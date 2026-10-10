"""Worker lifecycle and source acquisition outside workspace transactions."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import time
import unittest

from pmi_research_store import ResearchStore
from pmi_research_worker import run_once, start_worker
from pmi_review_store import ReviewStore
from test_research_store import bundle, pilot_payload


class ResearchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "worker.sqlite")
        self.review = ReviewStore(self.path)
        self.store = ResearchStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, count=1):
        self.review.initialize()
        self.review.import_payload(pilot_payload(count), "operator")
        return self.review.list_cases()

    def collector(self, case, previous):
        return bundle({"case": case})

    def test_unprepared_workspace_is_not_created_or_fetched(self):
        def forbidden(*args):
            self.fail("No source fetch before the operator workspace is prepared")
        self.assertEqual(run_once(self.store, collector=forbidden)["status"], "WAITING_FOR_WORKSPACE")
        self.assertFalse(Path(self.path).exists())

    def test_run_initializes_only_research_and_collects_one_case(self):
        self.load(3)
        calls = []
        def collector(case, previous):
            calls.append(case["case_id"])
            return self.collector(case, previous)
        self.assertEqual(run_once(self.store, collector=collector)["status"], "SUCCESS")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.status()["completed_count"], 1)

    def test_network_collector_holds_no_workspace_transaction(self):
        case = self.load()[0]
        def collector(candidate, previous):
            # A distinct write must finish while the collector is executing.
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.review.set_state, case["case_id"], "WAITING", "Concurrent operator review", "operator", "concurrent-note")
                future.result(timeout=3)
            self.assertEqual(candidate["case_id"], case["case_id"])
            return self.collector(candidate, previous)
        self.assertEqual(run_once(self.store, collector=collector)["status"], "SUCCESS")
        self.assertEqual(self.review.case(case["case_id"])["state"], "WAITING")

    def test_exception_is_sanitized_and_saved_without_losing_prior_work(self):
        case = self.load()[0]
        def failing(*args):
            raise RuntimeError("postgres://SECRET-password@private-host/property-private-name")
        result = run_once(self.store, collector=failing)
        self.assertEqual(result["status"], "ERROR")
        latest = self.store.latest(case["case_id"])
        self.assertNotIn("SECRET", str(latest))
        self.assertNotIn("private-host", str(latest))
        self.assertEqual(latest["sources"], [])
        self.assertEqual(self.review.case(case["case_id"])["seller_intent"], "UNKNOWN")
        self.assertEqual(run_once(self.store, collector=failing)["status"], "IDLE")

    def test_parallel_process_pollers_do_not_fetch_overlapping_cases(self):
        self.load(2)
        gate = threading.Event()
        started = threading.Event()
        calls = []
        def collector(case, previous):
            calls.append(case["case_id"])
            started.set()
            gate.wait(timeout=3)
            return self.collector(case, previous)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(run_once, self.store, collector=collector, worker_id="worker-1")
            self.assertTrue(started.wait(timeout=3))
            second = executor.submit(run_once, ResearchStore(self.path), collector=collector, worker_id="worker-2")
            self.assertEqual(second.result(timeout=3)["status"], "IDLE")
            gate.set()
            self.assertEqual(first.result(timeout=3)["status"], "SUCCESS")
        self.assertEqual(len(calls), 1)

    def test_malformed_collector_result_records_safe_failure_without_holding_lease(self):
        case = self.load()[0]
        result = run_once(self.store, collector=lambda *_: {"case_id": "wrong-case", "private": "private-error-detail"})
        self.assertEqual(result["status"], "ERROR")
        self.assertNotIn("private-error-detail", str(self.store.latest(case["case_id"])))
        self.assertEqual(run_once(self.store, collector=self.collector)["status"], "IDLE")

    def test_background_handle_runs_and_stops_without_sensitive_health(self):
        self.load()
        handle = start_worker(lambda: self.store, collector=self.collector, interval_seconds=0.02, startup_delay=0)
        deadline = time.monotonic() + 3
        try:
            while handle.health()["completed_runs"] == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            health = handle.health()
            self.assertTrue(health["started"])
            self.assertEqual(health["completed_runs"], 1)
            self.assertIsNotNone(health["last_poll_at"])
            self.assertNotIn(self.path, str(health))
            self.assertNotIn("property", str(health))
        finally:
            handle.stop()
        self.assertFalse(handle.health()["alive"])

    def test_startup_delay_is_interruptible_and_start_returns_promptly(self):
        start = time.monotonic()
        handle = start_worker(lambda: self.store, collector=self.collector, startup_delay=60)
        self.assertLess(time.monotonic() - start, 0.2)
        handle.stop()
        self.assertFalse(handle.health()["alive"])
        self.assertIsNone(handle.health()["last_poll_at"])


if __name__ == "__main__":
    unittest.main()
