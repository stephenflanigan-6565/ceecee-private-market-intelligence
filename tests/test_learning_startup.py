"""Production wiring and operational health without a live database/network."""
import importlib
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class LearningStartupTests(unittest.TestCase):
    def load(self, **overrides):
        values = {
            "CEECEE_ENV": "production",
            "DATABASE_URL": "postgresql://synthetic@database.invalid/pmi_fixture",
            "PMI_REVIEW_ACCESS_KEY": "synthetic-learning-startup-passphrase",
            "PMI_RESEARCH_ENABLED": "1",
        }
        values.update(overrides)
        self.previous = sys.modules.pop("web_app", None)
        self.addCleanup(self.restore)
        worker = Mock()
        worker.health.return_value = {
            "alive": True, "last_outcome": "IDLE", "completed_runs": 1,
            "learning_started": True, "learning_last_outcome": "CHANGED",
            "learning_last_poll_at": "2026-10-11T12:00:00+00:00",
            "learning_last_completed_at": "2026-10-11T12:00:00+00:00",
            "learning_refreshes": 1,
            "property_address": "MUST-NOT-APPEAR", "notes": "MUST-NOT-APPEAR",
        }
        with patch.dict(os.environ, values), patch("pmi_research_worker.start_worker", return_value=worker) as start:
            module = importlib.import_module("web_app")
            call = start.call_args
            calls = start.call_count
            # Factories select existing credentials, without opening storage.
            learning = call.kwargs["learning_factory"]() if call else None
            research = call.args[0]() if call else None
        return module, call, calls, learning, research

    def restore(self):
        sys.modules.pop("web_app", None)
        if self.previous is not None:
            sys.modules["web_app"] = self.previous

    def test_production_uses_same_worker_and_existing_database_for_learning(self):
        module, call, calls, learning, research = self.load()
        self.assertEqual(calls, 1)
        self.assertEqual(learning.dsn, research.dsn)
        self.assertIn("database.invalid", learning.dsn)
        data = module.app.test_client().get("/health").get_json()
        self.assertTrue(data["background_review_learning"]["started"])
        self.assertEqual(data["background_review_learning"]["last_outcome"], "CHANGED")
        self.assertEqual(data["background_review_learning"]["refreshes"], 1)
        self.assertNotIn("MUST-NOT-APPEAR", str(data))
        self.assertNotIn("synthetic@", str(data))

    def test_disabled_research_process_does_not_create_an_extra_learning_worker(self):
        module, _, calls, _, _ = self.load(PMI_RESEARCH_ENABLED="0")
        self.assertEqual(calls, 0)
        self.assertFalse(module.app.test_client().get("/health").get_json()["background_review_learning"]["configured"])

    def test_development_import_does_not_open_a_production_worker(self):
        _, _, calls, _, _ = self.load(CEECEE_ENV="development")
        self.assertEqual(calls, 0)


class PostgreSQLLearningAdapterTests(unittest.TestCase):
    def test_jsonpath_filter_is_bound_data_not_an_extra_driver_placeholder(self):
        from pmi_review_store import ReviewStore
        store = ReviewStore("postgresql://synthetic@database.invalid/fixture")
        connection = Mock()
        connection.execute.return_value.fetchall.return_value = [("fixture-case", "WAITING", "SYNTHETIC RD", "Check permit closeout.")]
        result = store._learning_cases(connection)
        query, params = connection.execute.call_args.args
        # psycopg must receive one value for its one SQL marker. JSONPath's
        # own question mark remains inside the bound value, not the SQL text.
        self.assertEqual(query.count("%s"), len(params))
        self.assertEqual(len(params), 1)
        self.assertIn("? (@.operator_review_eligible == true)", params[0])
        self.assertNotIn("? (@.", query)
        self.assertEqual(result[0]["next_check"], "Check permit closeout.")

    def test_database_connect_attempt_is_bounded_before_shared_worker_poll(self):
        from pmi_review_store import ReviewStore
        store = ReviewStore("postgresql://synthetic@database.invalid/fixture")
        connect = Mock()
        with patch.dict(sys.modules, {"psycopg": SimpleNamespace(connect=connect)}):
            store._connect()
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 5)


if __name__ == "__main__":
    unittest.main()
