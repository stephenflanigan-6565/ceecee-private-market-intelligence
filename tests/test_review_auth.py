"""Independent HTTP boundary tests, using no production records or database."""
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

import pmi_review
from pmi_review_store import ReviewStore


ACCESS_KEY = "synthetic-review-secret-0123456789"


class FakeStore:
    def __init__(self):
        self.calls = []
        self.initialized = False

    def ready(self):
        self.calls.append(("ready",))
        return self.initialized

    def initialize(self):
        self.calls.append(("initialize",))
        self.initialized = True

    def list_cases(self):
        self.calls.append(("list_cases",))
        return []

    def case(self, case_id):
        self.calls.append(("case", case_id))
        return None

    def export_payload(self):
        self.calls.append(("export_payload",))
        return {"private_test_record": "SYNTHETIC-ONLY"}

    def import_payload(self, payload, actor):
        self.calls.append(("import_payload", payload, actor))

    def set_state(self, case_id, state, note, actor, event_id):
        self.calls.append(("set_state", case_id, state, note, actor, event_id))

    def add_evidence(self, case_id, data, actor, event_id):
        self.calls.append(("add_evidence", case_id, data, actor, event_id))

    def review(self, case_id, data, actor, event_id):
        self.calls.append(("review", case_id, data, actor, event_id))


class ReviewAuthTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.store_factory_calls = 0
        self.source_calls = 0
        self.app = self.make_app()
        self.client = self.app.test_client()

    def factory(self):
        self.store_factory_calls += 1
        return self.store

    def loader(self):
        self.source_calls += 1
        return {"synthetic_snapshot": True}

    def make_app(self, *, key=ACCESS_KEY, allow_http=True, injected_store=True):
        app = Flask(__name__)
        app.config["TESTING"] = True
        with patch.dict("os.environ", {"PMI_REVIEW_OPERATOR_NAME": "Trusted operator"}):
            app.register_blueprint(pmi_review.create_blueprint(
                self.loader, access_key=key, allow_http=allow_http,
                store_factory=self.factory if injected_store else None,
            ))
        return app

    def token(self, response):
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match, "Rendered form must contain its CSRF token")
        return match.group(1)

    def login(self, client=None, *, base_url=None):
        client = client or self.client
        options = {"base_url": base_url} if base_url else {}
        page = client.get("/review", **options)
        response = client.post("/review/login", data={
            "csrf_token": self.token(page), "access_key": ACCESS_KEY,
        }, **options)
        self.assertEqual(303, response.status_code)
        return self.token(client.get("/review", **options))

    def assert_no_storage_or_source_access(self):
        self.assertEqual(0, self.store_factory_calls)
        self.assertEqual([], self.store.calls)
        self.assertEqual(0, self.source_calls)

    def test_missing_or_short_key_stays_locked_without_reading_records(self):
        for key in ("", "short"):
            with self.subTest(key=key):
                client = self.make_app(key=key).test_client()
                for path in ("/review", "/review/export", "/review/cases/anything"):
                    page = client.get(path)
                    self.assertEqual(200, page.status_code)
                    self.assertIn("safely locked", page.get_data(as_text=True))
                self.assertEqual(503, client.post("/review/initialize").status_code)
        self.assert_no_storage_or_source_access()

    def test_anonymous_reads_never_open_store_or_expose_export(self):
        self.assertEqual(200, self.client.get("/review").status_code)
        response = self.client.get("/review/export")
        self.assertEqual(302, response.status_code)
        self.assertNotIn("SYNTHETIC-ONLY", response.get_data(as_text=True))
        self.assertEqual(302, self.client.get("/review/cases/anything").status_code)
        self.assert_no_storage_or_source_access()

    def test_all_mutations_require_login_before_touching_store(self):
        paths = ("/review/initialize", "/review/import", "/review/logout",
                 "/review/cases/x/state", "/review/cases/x/evidence", "/review/cases/x/review")
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(401, self.client.post(path, data={"csrf_token": "fake"}).status_code)
        self.assert_no_storage_or_source_access()

    def test_login_requires_browser_seed_and_csrf_even_with_correct_secret(self):
        self.assertEqual(403, self.client.post("/review/login", data={"access_key": ACCESS_KEY}).status_code)
        page = self.client.get("/review")
        stolen_token = self.token(page)
        other_browser = self.app.test_client()
        self.assertEqual(403, other_browser.post("/review/login", data={
            "access_key": ACCESS_KEY, "csrf_token": stolen_token,
        }).status_code)
        self.assert_no_storage_or_source_access()

    def test_wrong_key_rejected_without_echoing_key_or_opening_store(self):
        page = self.client.get("/review")
        supplied = "wrong-secret-with-a-unicode-☃"
        response = self.client.post("/review/login", data={"access_key": supplied, "csrf_token": self.token(page)})
        self.assertEqual(401, response.status_code)
        self.assertNotIn(supplied, response.get_data(as_text=True))
        self.assertIsNone(self.client.get_cookie(pmi_review.COOKIE, path="/review"))
        self.assert_no_storage_or_source_access()

    def test_unicode_login_csrf_rejected_as_bad_form(self):
        self.client.get("/review")
        response = self.client.post("/review/login", data={"access_key": ACCESS_KEY, "csrf_token": "☃"})
        self.assertEqual(403, response.status_code)
        self.assert_no_storage_or_source_access()

    def test_authenticated_gets_never_initialize_import_or_save(self):
        self.login()
        self.store.calls.clear()
        self.client.get("/review")
        self.assertEqual(404, self.client.get("/review/cases/absent").status_code)
        self.assertEqual(200, self.client.get("/review/export").status_code)
        self.assertEqual(0, self.source_calls)
        self.assertTrue(all(call[0] in {"ready", "case", "list_cases", "export_payload"} for call in self.store.calls))
        self.assertFalse(self.store.initialized)

    def test_authenticated_mutations_reject_missing_wrong_and_unicode_csrf(self):
        self.login()
        self.store.calls.clear()
        before_factories = self.store_factory_calls
        for token in ("", "wrong", "☃"):
            with self.subTest(token=token):
                self.assertEqual(403, self.client.post("/review/initialize", data={"csrf_token": token}).status_code)
        self.assertEqual(before_factories, self.store_factory_calls)
        self.assertEqual([], self.store.calls)

    def test_csrf_is_bound_to_session_not_shared_access_key(self):
        token = self.login()
        other_browser = self.app.test_client()
        self.login(other_browser)
        self.store.calls.clear()
        self.assertEqual(403, other_browser.post("/review/initialize", data={"csrf_token": token}).status_code)
        self.assertEqual([], self.store.calls)

    def test_explicit_authenticated_initialization_and_import_use_server_actor(self):
        token = self.login()
        self.assertEqual(303, self.client.post("/review/initialize", data={"csrf_token": token}).status_code)
        self.assertEqual(303, self.client.post("/review/import", data={
            "csrf_token": token, "actor": "Forged owner", "source_url": "https://invalid.example/",
        }).status_code)
        self.assertEqual(1, self.source_calls)
        saved = next(call for call in self.store.calls if call[0] == "import_payload")
        self.assertEqual("Trusted operator", saved[-1])
        self.assertEqual({"synthetic_snapshot": True}, saved[1])

    def test_evidence_cannot_forge_reviewer_identity(self):
        token = self.login()
        response = self.client.post("/review/cases/x/evidence", data={
            "csrf_token": token, "event_id": "test-evidence", "actor": "Someone else",
            "field": "project_status", "value": "COMPLETED", "source_ref": "test-record",
            "observed_at": "2026-10-10", "verified": "on", "current": "on",
        })
        self.assertEqual(303, response.status_code)
        saved = next(call for call in self.store.calls if call[0] == "add_evidence")
        self.assertEqual("Trusted operator", saved[-2])
        self.assertNotIn("actor", saved[2])

    def test_tampered_session_never_reaches_store(self):
        self.login()
        self.client.set_cookie(pmi_review.COOKIE, "tampered-session", path="/review")
        self.store.calls.clear()
        before_factories = self.store_factory_calls
        self.assertEqual(401, self.client.post("/review/initialize", data={"csrf_token": "anything"}).status_code)
        self.assertEqual(before_factories, self.store_factory_calls)
        self.assertEqual([], self.store.calls)

    def test_server_expiry_invalidates_cookie_even_when_browser_keeps_it(self):
        with patch("itsdangerous.timed.time.time", return_value=2000000000):
            token = self.login()
        self.store.calls.clear()
        with patch("itsdangerous.timed.time.time", return_value=2000000000 + pmi_review.SESSION_SECONDS + 1):
            self.assertEqual(401, self.client.post("/review/initialize", data={"csrf_token": token}).status_code)
        self.assertEqual([], self.store.calls)

    def test_key_rotation_invalidates_old_session(self):
        token = self.login()
        old_cookie = self.client.get_cookie(pmi_review.COOKIE, path="/review")
        new_client = self.make_app(key="different-synthetic-secret-0123456789").test_client()
        new_client.set_cookie(pmi_review.COOKIE, old_cookie.value, path="/review")
        self.store.calls.clear()
        self.assertEqual(401, new_client.post("/review/initialize", data={"csrf_token": token}).status_code)
        self.assertEqual([], self.store.calls)

    def test_logout_clears_cookie_and_requires_csrf(self):
        token = self.login()
        self.assertEqual(403, self.client.post("/review/logout").status_code)
        self.assertIsNotNone(self.client.get_cookie(pmi_review.COOKIE, path="/review"))
        self.assertEqual(303, self.client.post("/review/logout", data={"csrf_token": token}).status_code)
        self.assertIsNone(self.client.get_cookie(pmi_review.COOKIE, path="/review"))
        self.assertEqual(401, self.client.post("/review/initialize", data={"csrf_token": token}).status_code)

    def test_secure_cookie_and_private_response_headers_on_production_blueprint(self):
        client = self.make_app(allow_http=False).test_client()
        page = client.get("/review", base_url="https://localhost")
        login_cookie = page.headers.get("Set-Cookie", "")
        for attribute in ("Secure", "HttpOnly", "SameSite=", "Path=/review"):
            self.assertIn(attribute, login_cookie)
        response = client.post("/review/login", base_url="https://localhost", data={
            "access_key": ACCESS_KEY, "csrf_token": self.token(page),
        })
        self.assertEqual(303, response.status_code)
        for attribute in ("Secure", "HttpOnly", "SameSite=", "Path=/review"):
            self.assertIn(attribute, response.headers.get("Set-Cookie", ""))
        self.assertEqual("no-store", response.headers["Cache-Control"])
        self.assertEqual("DENY", response.headers["X-Frame-Options"])
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_production_refuses_missing_or_sqlite_database_without_opening_it(self):
        for dsn in ("", "sqlite:///would-be-ephemeral.db"):
            with self.subTest(dsn=dsn), patch.dict("os.environ", {"DATABASE_URL": dsn}), patch.object(pmi_review, "ReviewStore") as constructor:
                client = self.make_app(allow_http=False, injected_store=False).test_client()
                page = client.get("/review", base_url="https://localhost")
                self.assertEqual(303, client.post("/review/login", base_url="https://localhost", data={
                    "access_key": ACCESS_KEY, "csrf_token": self.token(page),
                }).status_code)
                self.assertEqual(503, client.get("/review", base_url="https://localhost").status_code)
                constructor.assert_not_called()

    def test_database_unavailability_returns_safe_status_without_replacing_records(self):
        token = self.login()
        with patch.object(self.store, "ready", side_effect=sqlite3.OperationalError("synthetic private database detail")):
            response = self.client.get("/review")
        self.assertEqual(503, response.status_code)
        self.assertNotIn("synthetic private database detail", response.get_data(as_text=True))
        with patch.object(self.store, "initialize", side_effect=sqlite3.OperationalError("synthetic failure")):
            response = self.client.post("/review/initialize", data={"csrf_token": token})
        self.assertEqual(503, response.status_code)

    def test_real_store_missing_case_has_404_for_read_and_authenticated_save(self):
        with tempfile.TemporaryDirectory() as directory:
            self.store = ReviewStore(directory + "/review.db")
            self.store.initialize()
            token = self.login()
            self.assertEqual(404, self.client.get("/review/cases/missing").status_code)
            self.assertEqual(404, self.client.post("/review/cases/missing/state", data={
                "csrf_token": token, "state": "IN_REVIEW", "note": "synthetic note",
            }).status_code)
            self.assertEqual([], self.store.export_payload()["cases"])

    def test_real_store_rejects_cross_case_feedback_and_unattributed_owner_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.store = ReviewStore(directory + "/review.db")
            self.store.initialize()
            self.store.import_payload({
                "status": "ok", "version": "FIND4",
                "profile_payload": {"complete": True, "returned": 2, "total": 2},
                "profiles": [{
                    "parcel_id": "SYNTHETIC-" + str(index),
                    "property_address": str(index) + " SYNTHETIC TEST RD",
                    "why_pmi_noticed_it": [{
                        "route": "PROJECT_CONTEXT", "state": "ACTIVE_RESEARCH_ROUTE",
                        "actual_values": {"project_status": "COMPLETED", "current_use": "VACANT"},
                    }],
                } for index in (1, 2)],
            }, "Trusted operator")
            token = self.login()
            first, second = self.store.list_cases()
            analysis = self.store.case(first["case_id"])["analysis"]
            hypothesis = analysis["hypotheses"][0]
            before = self.store.export_payload()
            finding = {"csrf_token": token, "analysis_id": analysis["analysis_id"],
                       "hypothesis_id": hypothesis["hypothesis_id"], "detail": "synthetic finding",
                       "verified": "on", "method": "OPERATOR_REVIEW"}
            self.assertEqual(400, self.client.post("/review/cases/" + second["case_id"] + "/review", data={
                **finding, "outcome": "USEFUL_INVESTIGATION",
            }).status_code)
            self.assertEqual(400, self.client.post("/review/cases/" + first["case_id"] + "/review", data={
                **finding, "outcome": "SELLER_REASON_CONFIRMED",
            }).status_code)
            after = self.store.export_payload()
            self.assertEqual(before["memory"], after["memory"])
            self.assertEqual(before["cases"], after["cases"])

    def test_only_http_links_without_credentials_or_control_characters_render_as_sources(self):
        for url in ("https://records.example.test/property/123", "http://records.example.test/a?q=1"):
            with self.subTest(url=url):
                self.assertEqual(url, pmi_review.source_url(url))
        for url in (None, "javascript:alert(1)", "data:text/html,<script>x</script>", "//example.test/a",
                    "https://user:password@example.test/a", "https://example.test/\nattack", "not a URL"):
            with self.subTest(url=url):
                self.assertIsNone(pmi_review.source_url(url))


if __name__ == "__main__":
    unittest.main()
