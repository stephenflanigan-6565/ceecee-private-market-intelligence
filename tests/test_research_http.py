"""Research boundaries and real rendered pages; no remote calls or real records."""
import copy
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from pmi_review import create_blueprint
from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from pmi_case_sources import collect_case
from test_case_sources import FixtureFetch, PID, STAMP
from test_review_store import payload


KEY = "synthetic-research-access-passphrase-123"


class FakeResearch:
    def __init__(self):
        self.calls = []
        self.results = {}
        self.state = {"available": True, "enabled": True, "running": None,
                      "last_completed_at": None, "next_due_at": None,
                      "recent_runs": [], "pilot_count": 2, "completed_count": 0}
        self.queue_response = {"request_count": 1, "cooldown": False}

    def ready(self):
        self.calls.append(("ready",))
        return self.state["available"]

    def status(self):
        self.calls.append(("status",))
        return copy.deepcopy(self.state)

    def latest(self, case_id):
        self.calls.append(("latest", case_id))
        return copy.deepcopy(self.results.get(case_id))

    def set_enabled(self, enabled, actor):
        self.calls.append(("set_enabled", enabled, actor))
        self.state["enabled"] = enabled
        return copy.deepcopy(self.state)

    def request_run(self, case_id, actor):
        self.calls.append(("request_run", case_id, actor))
        return self.queue_response

    def initialize(self):
        raise AssertionError("HTTP requests must never initialize research")

    def claim_next(self, *args, **kwargs):
        raise AssertionError("HTTP requests must never start acquisition")


class ResearchHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.review = ReviewStore(str(Path(self.tmp.name) / "research-http.db"))
        self.review.initialize()
        self.review.import_payload(payload(2), "Synthetic operator")
        self.ids = [case["case_id"] for case in self.review.list_cases()]
        self.research = FakeResearch()
        self.research_factory_calls = 0
        self.app = self.make_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def factory(self):
        self.research_factory_calls += 1
        return self.research

    def make_app(self, *, default_research=False):
        app = Flask(__name__)
        app.config["TESTING"] = True
        with patch.dict("os.environ", {"PMI_REVIEW_OPERATOR_NAME": "Trusted research operator"}):
            app.register_blueprint(create_blueprint(lambda: payload(2),
                                   store_factory=lambda: self.review,
                                   research_factory=None if default_research else self.factory,
                                   access_key=KEY, allow_http=True))
        return app

    @staticmethod
    def token(response):
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True))
        if not match:
            raise AssertionError("Expected a rendered protected form")
        return match.group(1)

    def login(self, client=None):
        client = client or self.client
        page = client.get("/review")
        response = client.post("/review/login", data={"csrf_token": self.token(page), "access_key": KEY})
        self.assertEqual(303, response.status_code)
        return self.token(client.get("/review"))

    def review_snapshot(self):
        result = self.review.export_payload()
        result.pop("generated_at", None)
        return result

    def test_anonymous_research_actions_do_not_open_research_storage(self):
        for path in ("/review/research/toggle", "/review/research/run"):
            self.assertEqual(401, self.client.post(path, data={"enabled": "on", "case_id": self.ids[0]}).status_code)
        self.assertEqual(0, self.research_factory_calls)
        self.assertEqual([], self.research.calls)

    def test_research_actions_require_session_csrf(self):
        self.login()
        self.research.calls.clear()
        factories = self.research_factory_calls
        for path in ("/review/research/toggle", "/review/research/run"):
            for token in ("", "invalid", "☃"):
                self.assertEqual(403, self.client.post(path, data={"csrf_token": token, "enabled": "on"}).status_code)
        self.assertEqual(factories, self.research_factory_calls)
        self.assertEqual([], self.research.calls)

    def test_authenticated_gets_only_read_research(self):
        self.login()
        self.research.calls.clear()
        before = self.review_snapshot()
        self.assertEqual(200, self.client.get("/review").status_code)
        self.assertEqual(200, self.client.get("/review/cases/" + self.ids[0]).status_code)
        self.assertEqual(before, self.review_snapshot())
        self.assertTrue(all(call[0] in {"status", "latest"} for call in self.research.calls))
        self.assertIn(("latest", self.ids[0]), self.research.calls)

    def test_get_does_not_create_research_tables_in_shared_sqlite_store(self):
        client = self.make_app(default_research=True).test_client()
        with patch("urllib.request.urlopen", side_effect=AssertionError("No network on GET")):
            self.login(client)
            self.assertEqual(200, client.get("/review/cases/" + self.ids[0]).status_code)
        self.assertFalse(ResearchStore(self.review.dsn).ready())
        with sqlite3.connect(self.review.path) as connection:
            names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertFalse(any(name.startswith("pmi_research_") for name in names))

    def test_real_shared_store_queue_is_durable_without_starting_acquisition(self):
        real = ResearchStore(self.review.dsn)
        real.initialize()  # Background-startup responsibility, explicit here.
        client = self.make_app(default_research=True).test_client()
        token = self.login(client)
        before = self.review_snapshot()
        with patch("urllib.request.urlopen", side_effect=AssertionError("Queueing must not fetch")):
            response = client.post("/review/research/run", data={"csrf_token": token, "case_id": self.ids[0]})
            self.assertEqual(303, response.status_code)
            self.assertEqual(200, client.get("/review/cases/" + self.ids[0]).status_code)
        self.assertEqual(before, self.review_snapshot())
        with sqlite3.connect(self.review.path) as connection:
            self.assertEqual((1,), connection.execute("SELECT requested FROM pmi_research_schedule WHERE case_id=?", (self.ids[0],)).fetchone())
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM pmi_research_runs").fetchone()[0])
        self.assertEqual([], ResearchStore(self.review.dsn).history(self.ids[0]))

    def test_enabled_paused_running_and_recent_status_render(self):
        self.research.state.update(enabled=False, running={"property_address": "SYNTHETIC TEST ROAD"},
                                   last_completed_at="2026-10-10T01:02:00+00:00",
                                   recent_runs=[{"case_id": self.ids[0], "property_address": "SYNTHETIC TEST ROAD",
                                                 "status": "PARTIAL", "human_status": "Some records unavailable",
                                                 "completed_at": "2026-10-10T01:02:00+00:00"}])
        self.login()
        page = self.client.get("/review").get_data(as_text=True)
        for text in ("Paused", "Resume CC research", "SYNTHETIC TEST ROAD", "Some records unavailable", "2026-10-10T01:02:00+00:00"):
            self.assertIn(text, page)
        self.assertIn("Check pilot now", page)

    def test_authenticated_pause_and_resume_use_server_actor(self):
        token = self.login()
        for value, enabled in (("off", False), ("on", True)):
            response = self.client.post("/review/research/toggle", data={"csrf_token": token, "enabled": value,
                                                                        "actor": "Forged operator"})
            self.assertEqual(303, response.status_code)
            self.assertIn(("set_enabled", enabled, "Trusted research operator"), self.research.calls)

    def test_queue_all_or_current_case_does_not_acquire_or_change_review(self):
        token = self.login()
        before = self.review_snapshot()
        for case_id in (None, self.ids[0]):
            data = {"csrf_token": token, "actor": "Forged operator"}
            if case_id:
                data["case_id"] = case_id
            response = self.client.post("/review/research/run", data=data)
            self.assertEqual(303, response.status_code)
            self.assertIn(("request_run", case_id, "Trusted research operator"), self.research.calls)
            self.assertIn("queued", response.headers["Location"])
        self.assertEqual(before, self.review_snapshot())

    def test_property_queue_rejects_nonpilot_and_set_aside_cases(self):
        self.review.set_pilot(self.ids[0], False, "Synthetic operator", "remove-test")
        self.review.set_state(self.ids[1], "DISMISSED", "Synthetic dismissal", "Synthetic operator", "dismiss-test")
        token = self.login()
        self.research.calls.clear()
        for case_id in self.ids:
            self.assertEqual(400, self.client.post("/review/research/run", data={"csrf_token": token, "case_id": case_id}).status_code)
            page = self.client.get("/review/cases/" + case_id).get_data(as_text=True)
            self.assertNotIn("Check this property</button>", page)
        self.assertFalse(any(call[0] == "request_run" for call in self.research.calls))

    def test_missing_case_is_404_and_does_not_queue(self):
        token = self.login()
        self.research.calls.clear()
        self.assertEqual(404, self.client.post("/review/research/run", data={"csrf_token": token, "case_id": "missing"}).status_code)
        self.assertFalse(any(call[0] == "request_run" for call in self.research.calls))

    def test_cooldown_response_does_not_claim_new_check_was_started(self):
        token = self.login()
        self.research.queue_response = {"request_count": 0, "cooldown": True}
        response = self.client.post("/review/research/run", data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(200, response.status_code)
        self.assertIn("No new check was queued", response.get_data(as_text=True))

    def test_unready_research_does_not_initialize_on_post(self):
        self.research.state["available"] = False
        token = self.login()
        for path, data in (("/review/research/run", {}), ("/review/research/toggle", {"enabled": "on"})):
            response = self.client.post(path, data={"csrf_token": token, **data})
            self.assertEqual(409, response.status_code)
        self.assertFalse(any(call[0] in {"request_run", "set_enabled"} for call in self.research.calls))

    def test_read_failure_keeps_review_usable_without_exposing_database_detail(self):
        self.login()
        private = "postgresql://private-user:private-password@private-host/private-db"
        with patch.object(self.research, "status", side_effect=ValueError(private)):
            for path in ("/review", "/review/cases/" + self.ids[0]):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code)
                self.assertNotIn(private, response.get_data(as_text=True))
                self.assertIn("saved review work remains available", response.get_data(as_text=True))

    def test_queue_or_pause_failure_does_not_expose_database_detail(self):
        token = self.login()
        private = "postgresql://private-user:private-password@private-host/private-db"
        for method, path, data in (("request_run", "/review/research/run", {"case_id": self.ids[0]}),
                                  ("set_enabled", "/review/research/toggle", {"enabled": "off"})):
            with patch.object(self.research, method, side_effect=ValueError(private)):
                response = self.client.post(path, data={"csrf_token": token, **data})
                self.assertEqual(503, response.status_code)
                self.assertNotIn(private, response.get_data(as_text=True))

    def test_latest_failed_check_preserves_good_source_and_clear_dates(self):
        good = {"source_key": "owner", "source_name": "Official ownership records", "status": "SUCCESS",
                "complete": True, "observed_at": "2026-10-09T01:00:00+00:00",
                "last_successful_check_at": "2026-10-09T02:00:00+00:00", "expected_count": 1,
                "records": [{"owner_name": "SYNTHETIC RECORDED OWNER"}],
                "recorded_dates": {"transfer_date": ["2020-01-01"]},
                "change_summary": "First baseline: recorded ownership retained.",
                "query_url": "https://official.example.test/parcel/123", "citation": "Synthetic official record"}
        failed = {**good, "status": "ERROR", "complete": False, "observed_at": "2026-10-10T02:00:00+00:00",
                  "records": [], "recorded_dates": {}, "error": "Source did not respond.",
                  "change_summary": "The failed check cannot establish a record was removed.",
                  "query_url": "javascript:alert('bad')"}
        self.research.results[self.ids[0]] = {"status": "PARTIAL", "observed_at": failed["observed_at"],
                                            "sources": [failed], "retained_sources": [good],
                                            "findings": ["<script>unsafe source text</script>"],
                                            "next_checks": ["Confirm the recorded owner's connection to this parcel."],
                                            "change_summary": "Some source records were unavailable."}
        self.login()
        page = self.client.get("/review/cases/" + self.ids[0]).get_data(as_text=True)
        for text in ("Last good record", "SYNTHETIC RECORDED OWNER", "Source did not respond.",
                     "Dates recorded by the source", "2020-01-01", "2026-10-09T02:00:00+00:00",
                     "2026-10-10T02:00:00+00:00", "Next decisive checks", "https://official.example.test/parcel/123"):
            self.assertIn(text, page)
        self.assertNotIn('<script>unsafe source text</script>', page)
        self.assertIn('&lt;script&gt;unsafe source text&lt;/script&gt;', page)
        self.assertNotIn('href="javascript:', page)
        research_section = page.split('id="cc-research"', 1)[1].split('id="findings"', 1)[0]
        self.assertNotIn("Operator verified", research_section)
        self.assertIn("do not establish motivation", research_section)

    def test_successful_current_record_does_not_duplicate_retained_record(self):
        good = {"source_key": "owner", "source_name": "Official ownership records", "status": "SUCCESS",
                "complete": True, "records": [{"owner_name": "SYNTHETIC ONCE OWNER"}], "observed_at": "2026-10-10"}
        self.research.results[self.ids[0]] = {"status": "SUCCESS", "sources": [good], "retained_sources": [good],
                                            "findings": [], "next_checks": [], "observed_at": "2026-10-10",
                                            "change_summary": "First baseline retained; no prior check to compare."}
        self.login()
        page = self.client.get("/review/cases/" + self.ids[0]).get_data(as_text=True)
        self.assertEqual(1, page.count("SYNTHETIC ONCE OWNER"))
        self.assertIn("First baseline retained", page)
        self.assertNotIn("Previous good records remain available", page)

    def test_real_collector_nested_changes_and_recorded_dates_are_readable(self):
        data = payload()
        data["profiles"][0]["parcel_id"] = PID
        self.review.import_payload(data, "Synthetic operator")
        case = next(item for item in self.review.list_cases() if item["parcel_id"] == PID)
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"][0]["OWNERNAME"] = "Synthetic first owner"
        fetch.records["TaxParcelTransferCurrent"][0].update(RECORDDATE=0, SALEDATE=86400000)
        baseline = collect_case(case, fetch_json=fetch, observed_at=STAMP)
        previous = copy.deepcopy({source["source_key"]: source for source in baseline["sources"]})
        fetch.records["TaxParcelOwner"][0]["OWNERNAME"] = "Synthetic corrected owner"
        bundle = collect_case(case, previous_sources=previous, fetch_json=fetch, observed_at=STAMP)
        self.research.results[case["case_id"]] = bundle
        self.login()
        page = self.client.get("/review/cases/" + case["case_id"]).get_data(as_text=True)
        changes = page.split('<span class="small-label">What changed</span>', 1)[1].split('</div>', 1)[0]
        self.assertIn("Recorded ownership", changes)
        self.assertIn(bundle["change_summary"]["owner"]["message"], changes)
        self.assertIn("Parcel record", changes)
        self.assertIn("Transfer history", changes)
        self.assertIn("Synthetic corrected owner", page)
        self.assertIn("1970-01-02", page)
        self.assertIn("Source record 1", page)
        self.assertIn("A recorded date describes the record", page)

    def test_invalid_controls_do_not_open_research_for_write(self):
        token = self.login()
        self.research.calls.clear()
        response = self.client.post("/review/research/toggle", data={"csrf_token": token, "enabled": "invented"})
        self.assertEqual(400, response.status_code)
        self.assertFalse(any(call[0] == "set_enabled" for call in self.research.calls))
        response = self.client.post("/review/research/run", data={"csrf_token": token, "case_id": "x" * 129})
        self.assertEqual(400, response.status_code)
        self.assertFalse(any(call[0] == "request_run" for call in self.research.calls))


if __name__ == "__main__":
    unittest.main()
