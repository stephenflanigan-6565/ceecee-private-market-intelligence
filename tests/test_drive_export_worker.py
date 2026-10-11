"""Private delivery shares the worker and never enables paused acquisition."""
import threading
import unittest
from unittest.mock import Mock, patch

from pmi_research_worker import start_worker


class DriveExportWorkerTests(unittest.TestCase):
    def test_export_only_runs_without_touching_research_factory(self):
        completed = threading.Event()
        store_factory = Mock(side_effect=AssertionError("Research remains disabled"))
        service = Mock()

        def poll(**kwargs):
            completed.set()
            return {"status": "VERIFIED", "review_count": 31,
                    "private": "private-property-owner", "json_url": "private-export-url"}

        service.poll.side_effect = poll
        handle = start_worker(store_factory, export_factory=lambda: service,
                              research_enabled=False, startup_delay=0)
        try:
            self.assertTrue(completed.wait(timeout=3))
        finally:
            handle.stop()
        store_factory.assert_not_called()
        health = handle.health()
        self.assertEqual(health["last_outcome"], "DISABLED")
        self.assertEqual(health["completed_runs"], 0)
        self.assertEqual(health["export_last_outcome"], "VERIFIED")
        self.assertEqual(health["export_verified_runs"], 1)
        self.assertIsNotNone(health["export_last_completed_at"])
        self.assertNotIn("private-property-owner", str(health))
        self.assertNotIn("json_url", health)

    def test_export_poll_interval_leaves_research_running_between_checks(self):
        clock = [0.0]
        completed = threading.Event()
        research_calls, export_calls = [], []
        service = Mock()

        def research(*args, **kwargs):
            research_calls.append("research")
            if len(research_calls) == 2:
                clock[0] = 119.0
            elif len(research_calls) == 3:
                clock[0] = 120.0
            return {"status": "SUCCESS"}

        def poll(**kwargs):
            export_calls.append("export")
            if len(export_calls) == 2:
                completed.set()
            return {"status": "IDLE"}

        service.poll.side_effect = poll
        with patch("pmi_research_worker.time.monotonic", side_effect=lambda: clock[0]), \
                patch("pmi_research_worker.run_once", side_effect=research):
            handle = start_worker(lambda: object(), export_factory=lambda: service,
                                  interval_seconds=0.01, startup_delay=0)
            try:
                self.assertTrue(completed.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(len(export_calls), 2)
        self.assertEqual(len(research_calls), 3)
        self.assertEqual(handle.health()["export_verified_runs"], 0)

    def test_export_failure_does_not_stop_research_or_learning(self):
        clock = [0.0]
        completed = threading.Event()
        researches, exports, learning = [], [], []
        service = Mock()
        learning_store = Mock()
        learning_store.ready.return_value = True

        def learn():
            learning.append("learning")
            return {"refreshed": False}

        learning_store.refresh_learning.side_effect = learn

        def research(*args, **kwargs):
            researches.append("research")
            if len(researches) >= 3:
                clock[0] = 120.0
            return {"status": "SUCCESS"}

        def poll(**kwargs):
            exports.append("export")
            if len(exports) == 1:
                raise RuntimeError("refresh-token-private-owner")
            completed.set()
            return {"status": "VERIFIED"}

        service.poll.side_effect = poll
        with patch("pmi_research_worker.time.monotonic", side_effect=lambda: clock[0]), \
                patch("pmi_research_worker.run_once", side_effect=research), \
                self.assertLogs("pmi_research_worker", level="WARNING") as captured:
            handle = start_worker(lambda: object(), export_factory=lambda: service,
                                  learning_factory=lambda: learning_store,
                                  interval_seconds=0.01, startup_delay=0)
            try:
                self.assertTrue(completed.wait(timeout=3))
            finally:
                handle.stop()
        self.assertEqual(len(exports), 2)
        self.assertGreaterEqual(len(researches), 3)
        self.assertGreaterEqual(len(learning), 1)
        self.assertEqual(handle.health()["export_verified_runs"], 1)
        self.assertNotIn("refresh-token", str(captured.output))
        self.assertNotIn("private-owner", str(handle.health()))

    def test_unknown_result_is_sanitized(self):
        completed = threading.Event()
        service = Mock()

        def poll(**kwargs):
            completed.set()
            return {"status": "private-secret-status"}

        service.poll.side_effect = poll
        handle = start_worker(lambda: None, export_factory=lambda: service,
                              research_enabled=False, startup_delay=0)
        try:
            self.assertTrue(completed.wait(timeout=3))
        finally:
            handle.stop()
        self.assertEqual(handle.health()["export_last_outcome"], "UNAVAILABLE")
        self.assertNotIn("private-secret", str(handle.health()))

    def test_cancelled_startup_touches_no_factory(self):
        research, learning, export = Mock(), Mock(), Mock()
        handle = start_worker(research, learning_factory=learning,
                              export_factory=export, startup_delay=60)
        handle.stop()
        research.assert_not_called()
        learning.assert_not_called()
        export.assert_not_called()
        self.assertFalse(handle.health()["export_started"])
        self.assertFalse(handle.health()["alive"])


if __name__ == "__main__":
    unittest.main()
