"""Production wiring and protected, read-only export status."""
import importlib
import os
import re
import sys
import unittest
from unittest.mock import Mock, patch

from flask import Flask
from pmi_review import create_blueprint


KEY = "synthetic-export-status-passphrase"
GOOGLE = {"PMI_GOOGLE_DRIVE_CLIENT_ID": "synthetic-client",
          "PMI_GOOGLE_DRIVE_CLIENT_SECRET": "synthetic-secret",
          "PMI_GOOGLE_DRIVE_REFRESH_TOKEN": "synthetic-refresh"}


class ExportStartupTests(unittest.TestCase):
    def load(self, **overrides):
        values = {"CEECEE_ENV": "production",
                  "DATABASE_URL": "postgresql://synthetic@database.invalid/export_fixture",
                  "PMI_REVIEW_ACCESS_KEY": KEY, "PMI_RESEARCH_ENABLED": "1",
                  **{key: "" for key in GOOGLE}, **overrides}
        previous = sys.modules.pop("web_app", None)

        def restore():
            sys.modules.pop("web_app", None)
            if previous is not None:
                sys.modules["web_app"] = previous
        self.addCleanup(restore)
        worker = Mock()
        worker.health.return_value = {
            "alive": True, "last_outcome": "IDLE", "learning_started": True,
            "export_started": True, "export_last_outcome": "VERIFIED",
            "export_last_completed_at": "2026-10-11T17:00:00+00:00",
            "export_verified_runs": 1, "json_id": "PRIVATE-FILE-ID",
            "json_url": "PRIVATE-LINK", "source_counts": {"private": 30},
            "client_secret": "synthetic-secret", "notes": "PRIVATE-NOTE",
        }
        with patch.dict(os.environ, values), patch("pmi_research_worker.start_worker", return_value=worker) as start:
            module = importlib.import_module("web_app")
            factories = start.call_args.kwargs if start.called else {}
            export = factories["export_factory"]() if factories.get("export_factory") else None
            learning = factories["learning_factory"]() if factories.get("learning_factory") else None
        return module, start, export, learning

    def test_configured_export_shares_worker_and_existing_database(self):
        module, start, export, learning = self.load(**GOOGLE)
        self.assertEqual(start.call_count, 1)
        self.assertEqual(export.store.dsn, learning.dsn)
        self.assertTrue(start.call_args.kwargs["research_enabled"])
        data = module.app.test_client().get("/health").get_json()
        self.assertTrue(data["background_research_export"]["configured"])
        self.assertEqual(data["background_research_export"]["last_outcome"], "VERIFIED")
        self.assertEqual(data["background_research_export"]["verified_runs"], 1)
        for forbidden in ("PRIVATE", "synthetic-secret", "database.invalid", "source_counts", "json_id"):
            self.assertNotIn(forbidden, str(data))

    def test_export_only_preserves_disabled_acquisition_and_learning(self):
        module, start, export, learning = self.load(**GOOGLE, PMI_RESEARCH_ENABLED="0")
        self.assertEqual(start.call_count, 1)
        self.assertIsNotNone(export)
        self.assertIsNone(learning)
        self.assertFalse(start.call_args.kwargs["research_enabled"])
        data = module.app.test_client().get("/health").get_json()
        self.assertFalse(data["background_research"]["configured"])
        self.assertFalse(data["background_research"]["started"])

    def test_partial_google_configuration_does_not_enable_uploads(self):
        module, start, export, _ = self.load(PMI_GOOGLE_DRIVE_CLIENT_ID="synthetic-client")
        self.assertEqual(start.call_count, 1)
        self.assertIsNone(export)
        self.assertFalse(module.app.test_client().get("/health").get_json()["background_research_export"]["configured"])

    def test_development_never_starts_production_export(self):
        _, start, _, _ = self.load(**GOOGLE, CEECEE_ENV="development")
        start.assert_not_called()


class ExportStatusHTTPTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.status.return_value = {"status": "ENABLED", "daily_enabled": True,
                                            "json_url": "https://drive.google.com/file/d/synthetic/view",
                                            "review_counts": {"properties_with_operator_work": 30}}
        self.factory = Mock(return_value=self.service)
        self.source = Mock(side_effect=AssertionError("Status must not collect property research"))
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(create_blueprint(self.source, export_factory=self.factory,
                                                access_key=KEY, allow_http=True))
        self.client = app.test_client()

    def login(self):
        page = self.client.get("/review/").get_data(as_text=True)
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', page).group(1)
        self.assertEqual(self.client.post("/review/login", data={"csrf_token": token, "access_key": KEY}).status_code, 303)

    def test_anonymous_status_cannot_read_records_or_links(self):
        self.assertEqual(self.client.get("/review/research-exports.json").status_code, 302)
        self.factory.assert_not_called()

    def test_authenticated_get_only_reads_persisted_status(self):
        self.login()
        response = self.client.get("/review/research-exports.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), self.service.status.return_value)
        self.service.status.assert_called_once_with()
        self.service.poll.assert_not_called()
        self.source.assert_not_called()
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_status_failure_hides_raw_runtime_details(self):
        self.login()
        self.service.status.side_effect = RuntimeError("private database credentials")
        response = self.client.get("/review/research-exports.json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "UNAVAILABLE")
        self.assertNotIn("private database credentials", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
