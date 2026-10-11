"""Synthetic saved-review learning, separate from production operator data."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pmi_review_store import ReviewStore
from pmi_learning import build_report
from test_review_store import payload, fact


class LearningStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "reviews.sqlite")
        self.store = ReviewStore("sqlite:///" + self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, count=1, seller=False):
        self.store.initialize()
        self.store.import_payload(payload(count, seller=seller), "synthetic-operator")
        return self.store.list_cases()

    def rows(self, table, where=""):
        with sqlite3.connect(self.path) as connection:
            return connection.execute("SELECT * FROM " + table + where).fetchall()

    def finding(self, case, event, outcome="USEFUL_INVESTIGATION", **updates):
        hypothesis = self.store.case(case["case_id"])["analysis"]["hypotheses"][0]
        data = {"analysis_id": case["analysis_id"], "hypothesis_id": hypothesis["hypothesis_id"],
                "outcome": outcome, "method": "OPERATOR_REVIEW", "detail": "Synthetic checked explanation.", "verified": True}
        data.update(updates)
        self.store.review(case["case_id"], data, "synthetic-operator", event)
        return data

    def test_missing_saved_projection_is_none_without_initializing(self):
        self.assertIsNone(self.store.learning_report())
        self.assertIsNone(self.store.refresh_learning())
        self.assertFalse(Path(self.path).exists())
        self.load()
        self.assertIsNone(self.store.learning_report())
        report = self.store.refresh_learning()
        self.assertEqual(report["status"], "NO_OPERATOR_REVIEWS")
        self.assertEqual(report["counts"]["total_properties"], 1)

    def test_thirty_notes_are_context_and_never_verified_learning(self):
        cases = self.load(30)
        for index, case in enumerate(cases):
            self.store.set_state(case["case_id"], "COMPLETE", "Synthetic note: I would sell that house.", "operator", "note-" + str(index))
        report = self.store.learning_report()
        self.assertEqual(report["status"], "NEEDS_STRUCTURED_FINDINGS")
        self.assertEqual(report["counts"]["properties_with_operator_work"], 30)
        self.assertEqual(report["counts"]["properties_with_notes"], 30)
        self.assertEqual(report["counts"]["properties_with_formal_reviews"], 0)
        self.assertEqual(report["counts"]["verified_review_events"], 0)
        self.assertEqual(report["workflow_stages"], {"COMPLETE": 30})
        self.assertEqual(report["verified_outcomes"], {})
        self.assertEqual(report["lessons"], [])
        self.assertEqual(report["suggestions"], [])
        self.assertTrue(all(item["learning_state"] == "NOTES_ONLY" for item in report["reviewed_cases"]))
        self.assertTrue(all(item["latest_note"] == "Synthetic note: I would sell that house." for item in report["reviewed_cases"]))
        self.assertIn("30 properties", report["next_checks"][0])
        self.assertFalse(report["guards"]["notes_promoted_to_facts"])
        self.assertTrue(all(self.store.case(case["case_id"])["seller_intent"] == "UNKNOWN" for case in cases))

    def test_mirrored_review_and_feedback_count_once(self):
        case = self.load(seller=True)[0]
        self.finding(case, "checked-once")
        report = self.store.learning_report()
        self.assertEqual(len(self.rows("pmi_review_events", " WHERE kind='REVIEW'")), 1)
        self.assertEqual(len(self.rows("pmi_ai_review_records", " WHERE kind='FEEDBACK'")), 1)
        self.assertEqual(report["counts"]["review_events"], 1)
        self.assertEqual(report["counts"]["verified_review_events"], 1)
        self.assertEqual(report["verified_outcomes"], {"USEFUL_INVESTIGATION": 1})
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["reviewed_cases"][0]["learning_state"], "VERIFIED_FINDINGS")
        self.assertFalse(report["suggestions"][0]["adopted"])

    def test_verified_negative_and_correction_preserve_history_and_latest_outcome(self):
        case = self.load(seller=True)[0]
        data = self.finding(case, "negative", "FALSE_POSITIVE")
        corrected = {**data, "outcome": "USEFUL_INVESTIGATION", "detail": "Synthetic correction from official source.", "supersedes": "negative"}
        self.store.review(case["case_id"], corrected, "operator", "correction")
        self.store.review(case["case_id"], {**corrected, "verified": False, "outcome": "SOURCE_ERROR", "supersedes": "correction"}, "operator", "unverified-newer")
        report = self.store.learning_report()
        self.assertEqual(report["counts"]["review_events"], 3)
        self.assertEqual(report["counts"]["verified_review_events"], 2)
        self.assertEqual(report["counts"]["unverified_review_events"], 1)
        self.assertEqual(report["verified_outcomes"], {"USEFUL_INVESTIGATION": 1})
        self.assertEqual(report["lessons"][0]["outcomes"], {"USEFUL_INVESTIGATION": 1})
        self.assertEqual(len(self.rows("pmi_review_events", " WHERE kind='REVIEW'")), 3)

    def test_refresh_same_inputs_reuses_timestamp_and_avoids_recursive_report_inputs(self):
        self.load()
        first = self.store.refresh_learning(actor="one")
        second = self.store.refresh_learning(actor="two")
        self.assertTrue(first.pop("refreshed"))
        self.assertFalse(second.pop("refreshed"))
        self.assertEqual(first, second)
        self.assertEqual(len(self.rows("pmi_ai_review_records", " WHERE kind='LEARNING_REPORT'")), 1)
        self.assertEqual(self.store.learning_report(), first)

    def test_read_only_projection_and_refresh_do_not_rewrite_any_operator_input(self):
        case = self.load(seller=True)[0]
        self.finding(case, "finding")
        tables = ("pmi_review_imports", "pmi_review_case_versions", "pmi_review_cases", "pmi_review_events")
        before = {table: self.rows(table) for table in tables}
        inputs = self.rows("pmi_ai_review_records", " WHERE kind!='LEARNING_REPORT'")
        with patch.object(self.store, "export_payload", side_effect=AssertionError("must not export")), patch("pmi_review_store.analyze", side_effect=AssertionError("must not analyze a case")):
            self.store.refresh_learning()
            bytes_before = Path(self.path).read_bytes()
            self.store.learning_report()
        self.assertEqual(Path(self.path).read_bytes(), bytes_before)
        self.assertEqual({table: self.rows(table) for table in tables}, before)
        self.assertEqual(self.rows("pmi_ai_review_records", " WHERE kind!='LEARNING_REPORT'"), inputs)

    def test_failed_derived_refresh_preserves_successful_save_and_logs_no_note_or_secret(self):
        case = self.load()[0]
        with patch.object(self.store, "refresh_learning", side_effect=RuntimeError("secret-content")), self.assertLogs("pmi_review_store", level="WARNING") as output:
            result = self.store.set_state(case["case_id"], "WAITING", "Synthetic private note.", "operator", "saved-state")
        self.assertEqual(result["state"], "WAITING")
        self.assertEqual(result["notes"][0]["data"]["note"], "Synthetic private note.")
        self.assertNotIn("secret-content", " ".join(output.output))
        self.assertNotIn("Synthetic private note", " ".join(output.output))

    def test_evidence_save_refreshes_without_promoting_unverified_evidence(self):
        case = self.load()[0]
        self.store.add_evidence(case["case_id"], fact(verified=False), "operator", "unverified-evidence")
        report = self.store.learning_report()
        self.assertEqual(report["counts"]["evidence_records"], 1)
        self.assertEqual(report["counts"]["review_events"], 0)
        self.assertEqual(report["status"], "NEEDS_STRUCTURED_FINDINGS")
        self.assertEqual(report["reviewed_cases"][0]["learning_state"], "EVIDENCE_ONLY")
        self.assertEqual(report["suggestions"], [])

    def test_concurrent_refreshes_save_one_snapshot_with_same_timestamp(self):
        self.load(3)
        with ThreadPoolExecutor(max_workers=5) as executor:
            reports = list(executor.map(lambda _: ReviewStore("sqlite:///" + self.path).refresh_learning(), range(5)))
        self.assertEqual(sum(report["refreshed"] for report in reports), 1)
        self.assertEqual(len({report["input_revision"] for report in reports}), 1)
        self.assertEqual(len({report["generated_at"] for report in reports}), 1)
        self.assertEqual(len(self.rows("pmi_ai_review_records", " WHERE kind='LEARNING_REPORT'")), 1)

    def test_new_operator_input_creates_new_immutable_report(self):
        case = self.load()[0]
        first = self.store.refresh_learning()
        self.store.set_state(case["case_id"], "IN_REVIEW", "Synthetic next source check.", "operator", "new-work")
        second = self.store.learning_report()
        self.assertNotEqual(first["input_revision"], second["input_revision"])
        self.assertEqual(second["counts"]["properties_with_operator_work"], 1)
        rows = self.rows("pmi_ai_review_records", " WHERE kind='LEARNING_REPORT'")
        self.assertEqual(len(rows), 2)
        self.assertIn(first["input_revision"], [json.loads(row[4])["input_revision"] for row in rows])

    def test_report_caps_display_without_truncating_workspace_counts(self):
        cases = [{"case_id": "case-" + str(i), "property_address": "Synthetic " + str(i), "state": "IN_REVIEW", "next_check": "Check a source."} for i in range(120)]
        events = [{"event_id": "note-" + str(i), "case_id": case["case_id"], "kind": "STATE", "recorded_at": "2026-10-10", "data": {"note": "Synthetic note."}} for i, case in enumerate(cases)]
        suggestions = [{"suggestion_id": str(i), "adopted": False} for i in range(32)]
        report = build_report(cases, events, [], [], suggestions, input_revision="synthetic", generated_at="2026-10-10")
        self.assertEqual(report["counts"]["properties_with_operator_work"], 120)
        self.assertEqual(len(report["reviewed_cases"]), 100)
        self.assertEqual(report["suggestion_count"], 32)
        self.assertEqual(len(report["suggestions"]), 25)

    def test_postgres_snapshot_waits_for_workspace_lock_before_freezing_inputs(self):
        calls = []
        class Connection:
            def execute(self, query):
                calls.append(query)
            def commit(self):
                calls.append("COMMIT")
            def rollback(self):
                calls.append("ROLLBACK")
            def close(self):
                calls.append("CLOSE")
        store = ReviewStore("postgresql://synthetic.invalid/test")
        with patch.object(store, "_connect", return_value=Connection()):
            with store._session(write=True, snapshot=True):
                calls.append("SNAPSHOT_READS")
        self.assertEqual(calls, ["SELECT pg_advisory_lock(73421609)", "COMMIT",
                                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ WRITE",
                                "SELECT pg_advisory_xact_lock(73421609)", "SNAPSHOT_READS", "COMMIT", "CLOSE"])


if __name__ == "__main__":
    unittest.main()
