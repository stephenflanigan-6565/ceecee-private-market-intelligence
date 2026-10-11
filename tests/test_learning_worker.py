"""Automatic review analysis shares the existing research worker safely."""
import threading
import unittest
from unittest.mock import patch

from pmi_research_worker import run_learning_once, start_worker


class LearningStore:
    def __init__(self, *, ready=True, result=None):
        self.is_ready = ready
        self.result = {"status": "READY", "refreshed": True} if result is None else result
        self.calls = 0

    def ready(self):
        return self.is_ready

    def refresh_learning(self):
        self.calls += 1
        return self.result


class LearningWorkerTests(unittest.TestCase):
    def test_missing_workspace_is_waiting_without_initialization(self):
        store = LearningStore(ready=False)
        self.assertEqual(run_learning_once(store), "WAITING")
        self.assertEqual(store.calls, 0)

    def test_refresh_flag_is_separate_from_report_findings(self):
        for findings in ("READY", "NO_OPERATOR_REVIEWS", "NEEDS_STRUCTURED_FINDINGS"):
            with self.subTest(findings=findings):
                self.assertEqual(run_learning_once(LearningStore(result={"status": findings, "refreshed": True})), "CHANGED")
                self.assertEqual(run_learning_once(LearningStore(result={"status": findings, "refreshed": False})), "UNCHANGED")

    def test_startup_refresh_precedes_research_without_exposing_report(self):
        order = []
        finished = threading.Event()
        store = LearningStore(result={"status": "READY", "refreshed": True,
                                     "reviewed_case_count": 31,
                                     "private_note": "private-owner-name"})

        def refresh():
            order.append("learning")
            return store

        def research(*args, **kwargs):
            order.append("research")
            finished.set()
            return {"status": "SUCCESS"}

        with patch("pmi_research_worker.run_once", side_effect=research):
            handle = start_worker(lambda: object(), learning_factory=refresh, startup_delay=0)
            try:
                self.assertTrue(finished.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(order, ["learning", "research"])
        health = handle.health()
        self.assertEqual(health["learning_last_outcome"], "CHANGED")
        self.assertEqual(health["learning_refreshes"], 1)
        self.assertEqual(health["completed_runs"], 1)
        self.assertTrue(health["learning_started"])
        self.assertIsNotNone(health["learning_last_completed_at"])
        self.assertNotIn("private-owner-name", str(health))
        self.assertNotIn("reviewed_case_count", health)

    def test_disabled_learning_preserves_research_lifecycle(self):
        finished = threading.Event()

        def research(*args, **kwargs):
            finished.set()
            return {"status": "IDLE"}

        with patch("pmi_research_worker.run_once", side_effect=research):
            handle = start_worker(lambda: object(), startup_delay=0)
            try:
                self.assertTrue(finished.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(handle.health()["last_outcome"], "IDLE")
        self.assertFalse(handle.health()["learning_started"])
        self.assertEqual(handle.health()["learning_refreshes"], 0)

    def test_default_interval_skips_unchanged_polls_until_due(self):
        clock = [0.0]
        research_calls = []
        finished = threading.Event()
        store = LearningStore(result={"status": "READY", "refreshed": False})

        def research(*args, **kwargs):
            research_calls.append(store.calls)
            if len(research_calls) == 1:
                clock[0] = 119.0
            elif len(research_calls) == 2:
                clock[0] = 120.0
            else:
                finished.set()
            return {"status": "IDLE"}

        with patch("pmi_research_worker.time.monotonic", side_effect=lambda: clock[0]), \
                patch("pmi_research_worker.run_once", side_effect=research):
            handle = start_worker(lambda: object(), learning_factory=lambda: store,
                                  interval_seconds=0.01, startup_delay=0)
            try:
                self.assertTrue(finished.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(research_calls, [1, 1, 2])
        self.assertEqual(handle.health()["learning_last_outcome"], "UNCHANGED")
        self.assertEqual(handle.health()["learning_refreshes"], 0)

    def test_failed_analysis_keeps_research_running_and_retries_safely(self):
        clock = [0.0]
        attempts = []
        research_calls = []
        finished = threading.Event()

        def learning():
            attempts.append("attempt")
            if len(attempts) == 1:
                raise RuntimeError("postgres://private-password@private-owner/property")
            return LearningStore()

        def research(*args, **kwargs):
            research_calls.append("research")
            if len(research_calls) == 1:
                clock[0] = 30.0
            else:
                finished.set()
            return {"status": "SUCCESS"}

        with patch("pmi_research_worker.time.monotonic", side_effect=lambda: clock[0]), \
                patch("pmi_research_worker.run_once", side_effect=research), \
                self.assertLogs("pmi_research_worker", level="WARNING") as captured:
            handle = start_worker(lambda: object(), learning_factory=learning,
                                  learning_interval_seconds=0.01,
                                  interval_seconds=0.01, startup_delay=0)
            try:
                self.assertTrue(finished.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(research_calls), 2)
        self.assertEqual(handle.health()["completed_runs"], 2)
        self.assertEqual(handle.health()["learning_refreshes"], 1)
        self.assertNotIn("private-password", str(captured.output))
        self.assertNotIn("private-owner", str(handle.health()))

    def test_analysis_exception_does_not_abort_current_research_poll(self):
        finished = threading.Event()
        store = LearningStore()

        def fail():
            raise RuntimeError("private-source-error")

        store.refresh_learning = fail

        def research(*args, **kwargs):
            finished.set()
            return {"status": "SUCCESS"}

        with patch("pmi_research_worker.run_once", side_effect=research), \
                self.assertLogs("pmi_research_worker", level="WARNING") as captured:
            handle = start_worker(lambda: object(), learning_factory=lambda: store, startup_delay=0)
            try:
                self.assertTrue(finished.wait(timeout=3))
            finally:
                handle.stop()
        health = handle.health()
        self.assertEqual(health["learning_last_outcome"], "UNAVAILABLE")
        self.assertEqual(health["last_outcome"], "SUCCESS")
        self.assertIsNone(health["learning_last_completed_at"])
        self.assertNotIn("private-source-error", str(captured.output))

    def test_research_failure_does_not_prevent_later_learning(self):
        clock = [0.0]
        finished = threading.Event()
        store = LearningStore()
        research_calls = []

        def research(*args, **kwargs):
            research_calls.append("research")
            if len(research_calls) == 1:
                clock[0] = 120.0
                raise RuntimeError("private-database-error")
            finished.set()
            return {"status": "IDLE"}

        with patch("pmi_research_worker.time.monotonic", side_effect=lambda: clock[0]), \
                patch("pmi_research_worker.run_once", side_effect=research), \
                self.assertLogs("pmi_research_worker", level="WARNING"):
            handle = start_worker(lambda: object(), learning_factory=lambda: store,
                                  interval_seconds=0.01, startup_delay=0)
            try:
                self.assertTrue(finished.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(store.calls, 2)
        self.assertEqual(handle.health()["learning_refreshes"], 2)
        self.assertEqual(handle.health()["last_outcome"], "IDLE")

    def test_startup_delay_cancels_both_tasks_without_touching_storage(self):
        def forbidden():
            self.fail("Cancelled startup must not connect to either store")

        handle = start_worker(forbidden, learning_factory=forbidden, startup_delay=60)
        handle.stop()
        self.assertFalse(handle.health()["alive"])
        self.assertFalse(handle.health()["learning_started"])
        self.assertIsNone(handle.health()["last_poll_at"])


if __name__ == "__main__":
    unittest.main()
