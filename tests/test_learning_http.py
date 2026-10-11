"""Learning view reads saved reports; only an authenticated refresh writes."""
import copy
import re
import unittest
from unittest.mock import patch

from flask import Flask

from pmi_review import create_blueprint


KEY = "synthetic-learning-view-passphrase-123"
SECRET_DETAIL = "postgresql://synthetic-private-user:private-value@internal-host/private-db"


def sample_report():
    return {
        "version": "PMI_REVIEW_LEARNING_V1", "input_revision": "synthetic-revision",
        "generated_at": "2026-10-11T14:30:00+00:00", "status": "READY",
        "counts": {"total_properties": 194, "properties_with_operator_work": 30,
                   "properties_with_notes": 29, "properties_with_formal_reviews": 2,
                   "review_events": 3, "verified_review_events": 2,
                   "unverified_review_events": 1, "evidence_records": 4},
        "workflow_stages": {"COMPLETE": 30, "NEW": 164},
        "verified_outcomes": {"FALSE_POSITIVE": 1, "USEFUL_INVESTIGATION": 1},
        "lessons": [{"pattern": "LEASE_TERM_TRANSITION", "reviewed_properties": 2,
                     "outcomes": {"FALSE_POSITIVE": 1, "USEFUL_INVESTIGATION": 1}}],
        "suggestion_count": 1,
        "suggestions": [{"suggestion_id": "synthetic-candidate", "reviewed_properties": 2,
                         "conditions": [{"field": "lease_status", "value": "EXPIRED"}],
                         "outcomes": {"FALSE_POSITIVE": 1, "USEFUL_INVESTIGATION": 1},
                         "approved": False, "adopted": False}],
        "reviewed_cases": [{"case_id": "synthetic-case", "property_address": "30 SYNTHETIC TEST ROAD",
                            "state": "COMPLETE", "note_count": 1, "review_count": 1,
                            "verified_review_count": 1, "evidence_count": 2,
                            "learning_state": "VERIFIED_FINDINGS",
                            "latest_note": "<script>synthetic unsafe note</script>",
                            "next_check": "Check the recorded lease expiry against the current agreement."}],
        "next_checks": ["Record what disproved the first explanation."],
        "guards": {"seller_scoring": False, "outreach_touched": False, "patterns_adopted": False},
    }


class LearningStore:
    def __init__(self):
        self.calls = []
        self.available = True
        self.report = sample_report()

    def ready(self):
        self.calls.append(("ready",))
        return self.available

    def list_cases(self):
        self.calls.append(("list_cases",))
        return [{"case_id": "synthetic-case", "pilot": True, "lane": "PROPERTY_RESEARCH"}]

    def learning_report(self):
        self.calls.append(("learning_report",))
        return copy.deepcopy(self.report)

    def refresh_learning(self, actor=None):
        self.calls.append(("refresh_learning", actor))
        return copy.deepcopy(self.report)

    def export_payload(self):
        self.calls.append(("export_payload",))
        return {"version": "SYNTHETIC_BACKUP", "cases": []}

    def initialize(self):
        raise AssertionError("The learning view must not initialize storage")


class LearningHTTPTests(unittest.TestCase):
    def setUp(self):
        self.store = LearningStore()
        self.factory_calls = 0
        self.source_calls = 0
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        with patch.dict("os.environ", {"PMI_REVIEW_OPERATOR_NAME": "Trusted learning operator"}):
            self.app.register_blueprint(create_blueprint(self.loader, store_factory=self.factory,
                                       access_key=KEY, allow_http=True))
        self.client = self.app.test_client()

    def factory(self):
        self.factory_calls += 1
        return self.store

    def loader(self):
        self.source_calls += 1
        raise AssertionError("Learning reads must not refresh external property research")

    @staticmethod
    def token(response):
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True))
        if not match:
            raise AssertionError("Protected forms need a session token")
        return match.group(1)

    def login(self):
        page = self.client.get("/review/")
        response = self.client.post("/review/login", data={"csrf_token": self.token(page), "access_key": KEY})
        self.assertEqual(303, response.status_code)
        return self.token(self.client.get("/review/learning"))

    def test_anonymous_learning_cannot_open_store_or_read_report(self):
        for path in ("/review/learning", "/review/learning.json"):
            self.assertEqual(302, self.client.get(path).status_code)
        self.assertEqual(401, self.client.post("/review/learning/refresh").status_code)
        self.assertEqual(0, self.factory_calls)
        self.assertEqual([], self.store.calls)

    def test_get_reads_latest_snapshot_without_refresh_initialization_or_sources(self):
        self.login()
        self.store.calls.clear()
        for path in ("/review/learning", "/review/learning.json"):
            self.assertEqual(200, self.client.get(path).status_code)
        self.assertEqual(0, self.source_calls)
        self.assertTrue(all(call[0] in {"ready", "list_cases", "learning_report"} for call in self.store.calls))
        self.assertEqual(self.store.report, self.client.get("/review/learning.json").get_json())

    def test_render_actual_work_counts_checked_outcomes_and_property_links(self):
        self.login()
        page = self.client.get("/review/learning").get_data(as_text=True)
        for expected in ("Properties with saved work", "30 <span>of 194</span>", "29</dd>",
                         "2</dd>", "30 SYNTHETIC TEST ROAD", "/review/cases/synthetic-case",
                         "Check the recorded lease expiry", "Candidate · not adopted",
                         "False positive: 1", "Useful investigation: 1", "Lease Status", "EXPIRED",
                         "Oct 11, 2026 at 10:30 AM EDT", 'aria-current="page"><span>Review learning'):
            self.assertIn(expected, page)
        self.assertNotIn('<script>synthetic unsafe note</script>', page)
        self.assertIn('&lt;script&gt;synthetic unsafe note&lt;/script&gt;', page)
        self.assertNotIn("Seller score", page)
        self.assertNotIn("Adopt pattern", page)

    def test_missing_snapshot_preparing_does_not_forge_empty_counts(self):
        self.store.report = None
        self.login()
        page = self.client.get("/review/learning").get_data(as_text=True)
        self.assertIn("Automatic review analysis is preparing", page)
        self.assertIn("Check saved reviews", page)
        self.assertNotIn("0 <span>of 0</span>", page)
        result = self.client.get("/review/learning.json").get_json()
        self.assertEqual("PREPARING", result["status"])
        self.assertNotIn("counts", result)
        self.assertFalse(any(call[0] == "refresh_learning" for call in self.store.calls))

    def test_notes_only_preserve_work_and_ask_for_checked_findings(self):
        self.store.report.update(status="NEEDS_STRUCTURED_FINDINGS", lessons=[], suggestions=[],
                                 suggestion_count=0, verified_outcomes={})
        self.store.report["counts"].update(properties_with_formal_reviews=0, review_events=0,
                                          verified_review_events=0, unverified_review_events=0)
        self.store.report["reviewed_cases"][0].update(review_count=0, verified_review_count=0,
                                                    learning_state="NOTES_ONLY")
        self.login()
        page = self.client.get("/review/learning").get_data(as_text=True)
        self.assertIn("Saved work needs checked findings", page)
        self.assertIn("Your saved work is retained", page)
        self.assertIn("Record a checked finding", page)
        self.assertIn("29</dd>", page)
        self.assertNotIn("Lessons and candidate patterns", page)

    def test_refresh_requires_session_csrf_before_any_store_access(self):
        self.login()
        self.store.calls.clear()
        calls = self.factory_calls
        for token in ("", "wrong", "☃"):
            self.assertEqual(403, self.client.post("/review/learning/refresh", data={"csrf_token": token}).status_code)
        self.assertEqual(calls, self.factory_calls)
        self.assertEqual([], self.store.calls)

    def test_explicit_refresh_uses_server_actor_then_redirects_to_read_snapshot(self):
        token = self.login()
        self.store.calls.clear()
        response = self.client.post("/review/learning/refresh", data={"csrf_token": token, "actor": "Forged operator"})
        self.assertEqual(303, response.status_code)
        self.assertIn("/review/learning?", response.headers["Location"])
        self.assertEqual([("ready",), ("refresh_learning", "Trusted learning operator")], self.store.calls)
        self.assertEqual(0, self.source_calls)

    def test_refresh_unready_storage_does_not_initialize_or_refresh(self):
        token = self.login()
        self.store.available = False
        self.store.calls.clear()
        response = self.client.post("/review/learning/refresh", data={"csrf_token": token})
        self.assertEqual(409, response.status_code)
        self.assertIn("Review analysis is preparing", response.get_data(as_text=True))
        self.assertFalse(any(call[0] == "refresh_learning" for call in self.store.calls))

    def test_optional_mock_store_without_learning_methods_still_has_pending_page(self):
        self.login()
        class LegacyStore:
            def ready(self):
                return True
            def list_cases(self):
                return []
        with patch.object(self, "store", LegacyStore()):
            response = self.client.get("/review/learning")
            self.assertEqual(200, response.status_code)
            self.assertIn("Automatic review analysis is preparing", response.get_data(as_text=True))

    def test_analysis_failure_keeps_safe_view_and_previous_snapshot(self):
        token = self.login()
        with patch.object(self.store, "refresh_learning", side_effect=RuntimeError(SECRET_DETAIL)):
            response = self.client.post("/review/learning/refresh", data={"csrf_token": token})
        self.assertEqual(503, response.status_code)
        page = response.get_data(as_text=True)
        self.assertNotIn(SECRET_DETAIL, page)
        self.assertIn("Review analysis could not finish", page)
        self.assertIn("30 SYNTHETIC TEST ROAD", page)

    def test_report_read_failure_does_not_expose_private_exception(self):
        self.login()
        with patch.object(self.store, "learning_report", side_effect=RuntimeError(SECRET_DETAIL)):
            for path in ("/review/learning", "/review/learning.json"):
                response = self.client.get(path)
                self.assertEqual(503, response.status_code)
                self.assertNotIn(SECRET_DETAIL, response.get_data(as_text=True))

    def test_authenticated_backup_includes_snapshot_without_refresh(self):
        self.login()
        self.store.calls.clear()
        response = self.client.get("/review/export")
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.store.report, response.get_json()["learning"])
        self.assertIn("PMI-review-backup.json", response.headers["Content-Disposition"])
        self.assertEqual([("export_payload",), ("learning_report",)], self.store.calls)

    def test_backup_remains_available_when_learning_read_fails(self):
        self.login()
        with patch.object(self.store, "learning_report", side_effect=RuntimeError(SECRET_DETAIL)):
            response = self.client.get("/review/export")
        self.assertEqual(200, response.status_code)
        self.assertEqual("UNAVAILABLE", response.get_json()["learning"]["status"])
        self.assertEqual([], response.get_json()["cases"])
        self.assertNotIn(SECRET_DETAIL, response.get_data(as_text=True))

    def test_learning_responses_use_existing_private_headers(self):
        self.login()
        for path in ("/review/learning", "/review/learning.json"):
            response = self.client.get(path)
            self.assertEqual("no-store", response.headers["Cache-Control"])
            self.assertEqual("DENY", response.headers["X-Frame-Options"])


if __name__ == "__main__":
    unittest.main()
