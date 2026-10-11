"""Complete export reconciliation over temporary databases, never live reviews."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from pmi_research_export import (build_summary, exported_counts, review_counts,
                                 source_revision, validate_snapshot)
from seller_ai_memory import canonical
from test_research_store import pilot_payload, bundle
from test_review_store import fact


class ResearchExportSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "snapshot.sqlite")
        self.review = ReviewStore(self.path)
        self.research = ResearchStore(self.path)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, count=1):
        self.review.initialize()
        self.review.import_payload(pilot_payload(count), "synthetic-operator")
        self.research.initialize()
        return self.review.list_cases()

    def complete(self, owner="Synthetic original owner", offset=0):
        instant = self.now + timedelta(days=offset)
        claim = self.research.claim_next("synthetic-worker", now=instant)
        data = bundle(claim, owner=owner)
        self.research.finish(claim["run_id"], claim["lease_token"], data, now=instant)
        return claim

    def rehash(self, data):
        data["source_revision"] = source_revision(data)
        data["review_counts"] = review_counts(data)
        return data

    def test_snapshot_exports_all_properties_beyond_learning_display_cap(self):
        self.load(110)
        snapshot = self.review.research_export_snapshot()
        self.assertEqual(len(snapshot["cases"]), 110)
        self.assertEqual(len(snapshot["case_versions"]), 110)
        self.assertEqual(snapshot["review_counts"]["total_properties"], 110)
        self.assertEqual(snapshot["manifest"]["source_counts"], exported_counts(snapshot))
        self.assertEqual(snapshot["manifest"]["source_counts"], snapshot["manifest"]["exported_counts"])
        self.assertEqual(len(snapshot["manifest"]["source_counts"]), 10)
        self.assertIs(validate_snapshot(snapshot), snapshot)

    def test_full_history_sources_reviews_corrections_and_exact_notes_retained(self):
        case = self.load()[0]
        note = "Synthetic owner's note: check official source before deciding."
        self.review.set_state(case["case_id"], "WAITING", note, "operator", "note")
        self.review.add_evidence(case["case_id"], fact(), "operator", "project")
        qualified = self.review.add_evidence(case["case_id"], fact("current_use", "VACANT"), "operator", "vacant")
        hypothesis = qualified["analysis"]["hypotheses"][0]
        finding = {"analysis_id": qualified["analysis_id"], "hypothesis_id": hypothesis["hypothesis_id"],
                   "outcome": "FALSE_POSITIVE", "method": "OPERATOR_REVIEW", "detail": "Synthetic negative.", "verified": True}
        self.review.review(case["case_id"], finding, "operator", "finding")
        self.review.review(case["case_id"], {**finding, "supersedes": "finding", "outcome": "USEFUL_INVESTIGATION", "detail": "Synthetic sourced correction."}, "operator", "corrected")
        first = self.complete()
        self.complete(owner="Synthetic changed owner", offset=1)
        snapshot = self.review.research_export_snapshot()
        histories = snapshot["cases"][0]["history"]
        self.assertEqual(next(event["data"]["note"] for event in histories if event["event_id"] == "note"), note)
        self.assertGreater(len(snapshot["case_versions"]), 1)
        self.assertEqual(snapshot["review_counts"]["review_events"], 2)
        self.assertEqual(snapshot["review_counts"]["verified_review_events"], 2)
        self.assertEqual(snapshot["review_counts"]["verified_outcomes"], {"USEFUL_INVESTIGATION": 1})
        self.assertEqual(len(snapshot["research"]["runs"]), 2)
        self.assertEqual(len(snapshot["research"]["source_snapshots"]), 2)
        self.assertEqual(len(snapshot["research"]["source_pointers"]), 1)
        self.assertEqual(snapshot["research"]["source_pointers"][0]["source"]["records"][0]["OWNERNME1"], "Synthetic changed owner")
        self.assertNotIn(first["lease_token"], json.dumps(snapshot))
        self.assertNotIn("worker_id", json.dumps(snapshot))
        self.assertNotIn(self.path, json.dumps(snapshot))

    def test_clock_and_delivery_ledger_do_not_change_source_revision(self):
        self.load()
        first = self.review.research_export_snapshot()
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO pmi_ai_review_records VALUES(?,?,?,?,?,?)", ("drive:synthetic", "DRIVE_EXPORT_RECEIPT", "workspace:daily-export", "", canonical({"file_id": "synthetic-file", "source_revision": first["source_revision"]}), self.now.isoformat()))
        second = self.review.research_export_snapshot()
        self.assertEqual(first["source_revision"], second["source_revision"])
        self.assertEqual(first["manifest"]["source_counts"], second["manifest"]["source_counts"])
        self.assertFalse(any(item["kind"].startswith("DRIVE_EXPORT_") for item in second["memory"]))
        self.assertEqual(second["manifest"]["excluded_operational_memory_prefix"], "DRIVE_EXPORT_")

    def test_readonly_snapshot_and_failed_validation_leave_database_unchanged(self):
        self.load()
        before = Path(self.path).read_bytes()
        with patch("pmi_review_store.analyze", side_effect=AssertionError("Must not reanalyze")):
            self.review.research_export_snapshot()
        self.assertEqual(Path(self.path).read_bytes(), before)
        with patch("pmi_research_export.validate_snapshot", side_effect=ValueError("Synthetic validation failure")):
            with self.assertRaises(ValueError):
                self.review.research_export_snapshot()
        self.assertEqual(Path(self.path).read_bytes(), before)

    def test_concurrent_saved_review_does_not_mix_snapshot_counts_with_new_rows(self):
        case = self.load()[0]
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
        first = self.review.research_export_snapshot()
        original = self.review._export_payload_from_connection
        saved = []
        def during_snapshot(connection, *, full=False):
            if not saved:
                saved.append(True)
                ReviewStore(self.path).set_state(case["case_id"], "COMPLETE", "Synthetic concurrent saved work.", "operator", "concurrent-note")
            return original(connection, full=full)
        # The source COUNT queries already established the readonly snapshot.
        with patch.object(ReviewStore, "_export_payload_from_connection", autospec=True, side_effect=lambda instance, connection, full=False: during_snapshot(connection, full=full)):
            coherent = self.review.research_export_snapshot()
        later = self.review.research_export_snapshot()
        self.assertEqual(coherent["source_revision"], first["source_revision"])
        self.assertEqual(coherent["review_counts"]["properties_with_operator_work"], 0)
        self.assertEqual(later["review_counts"]["properties_with_operator_work"], 1)
        self.assertNotEqual(later["source_revision"], coherent["source_revision"])

    def test_tampered_hash_counts_and_dangling_reference_rejected(self):
        self.load()
        valid = self.review.research_export_snapshot()
        bad = copy.deepcopy(valid)
        bad["cases"][0]["state"] = "COMPLETE"
        with self.assertRaises(ValueError):
            validate_snapshot(bad)
        bad = copy.deepcopy(valid)
        bad["manifest"]["source_counts"]["pmi_review_cases"] += 1
        with self.assertRaises(ValueError):
            validate_snapshot(bad)
        bad = copy.deepcopy(valid)
        bad["cases"][0]["version_id"] = "missing-version"
        self.rehash(bad)
        with self.assertRaises(ValueError):
            validate_snapshot(bad)
        bad = copy.deepcopy(valid)
        bad["cases"][0]["baseline"]["narrative"] = "Synthetic mismatched pointer data."
        self.rehash(bad)
        with self.assertRaises(ValueError):
            validate_snapshot(bad)

    def test_orphan_source_rows_fail_completeness_instead_of_disappearing(self):
        self.load()
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO pmi_review_events VALUES(?,?,?,?,?)", ("orphan", "missing-case", "STATE", canonical({"state": "NEW", "note": "Synthetic orphan."}), self.now.isoformat()))
        with self.assertRaises(ValueError):
            self.review.research_export_snapshot()

    def test_explicit_credential_fields_excluded_and_original_database_preserved(self):
        self.review.initialize()
        data = pilot_payload()
        data["api_key"] = "synthetic-secret-not-to-export"
        self.review.import_payload(data, "operator")
        self.research.initialize()
        snapshot = self.review.research_export_snapshot()
        self.assertNotIn("synthetic-secret-not-to-export", json.dumps(snapshot))
        self.assertNotIn("api_key", snapshot["imports"][0]["payload"])
        self.assertEqual(self.review.export_payload()["imports"][0]["payload"]["api_key"], "synthetic-secret-not-to-export")

    def test_summary_distinguishes_notes_and_saved_completion_from_verified_learning(self):
        case = self.load()[0]
        self.review.set_state(case["case_id"], "COMPLETE", "Synthetic opinion only.", "operator", "note")
        snapshot = self.review.research_export_snapshot()
        summary = build_summary(snapshot)
        self.assertIn("Workflow marked complete: 1", summary)
        self.assertIn("no formal finding: 1", summary)
        self.assertIn("No verified formal outcome", summary)
        self.assertIn(snapshot["source_revision"], summary)
        self.assertNotIn("motivated seller", summary)

    def test_missing_tables_are_not_initialized_by_snapshot(self):
        with self.assertRaises(sqlite3.Error):
            self.review.research_export_snapshot()
        self.assertFalse(Path(self.path).exists())

    def test_postgres_snapshot_is_repeatable_read_readonly_without_lock_or_writes(self):
        calls = []
        class Connection:
            def execute(self, query):
                calls.append(query)
            def close(self):
                calls.append("CLOSE")
        store = ReviewStore("postgresql://synthetic.invalid/database")
        with patch.object(store, "_connect", return_value=Connection()):
            with store._session(snapshot=True):
                calls.append("READ_ALL_TABLES")
        self.assertEqual(calls, ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", "READ_ALL_TABLES", "CLOSE"])


if __name__ == "__main__":
    unittest.main()
