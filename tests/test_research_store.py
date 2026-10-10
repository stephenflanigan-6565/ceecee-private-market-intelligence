"""Durable scheduling and immutable source evidence, using synthetic records."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pmi_research_store import ResearchStore
from pmi_review_store import ReviewStore
from test_review_store import payload


def pilot_payload(count=1):
    data = payload(count)
    for index, profile in enumerate(data["profiles"]):
        profile["parcel_id"] = "090000000000000" + str(index).zfill(4)
    return data


def bundle(claim, *, status="SUCCESS", owner="Synthetic owner", source_status="SUCCESS"):
    return {"case_id": claim["case"]["case_id"], "parcel_id": claim["case"]["parcel_id"],
            "observed_at": datetime.now(timezone.utc).isoformat(), "status": status,
            "sources": [{"source_key": "owner", "source_name": "Synthetic official owners",
                         "query_url": "https://example.test/official-record", "citation": "Synthetic source",
                         "observed_at": datetime.now(timezone.utc).isoformat(),
                         "status": source_status, "complete": source_status in {"SUCCESS", "EMPTY"},
                         "expected_count": 1 if source_status == "SUCCESS" else 0,
                         "records": [{"OBJECTID": 7, "PARCELID": claim["case"]["parcel_id"], "OWNERNME1": owner}] if source_status == "SUCCESS" else [],
                         "content_hash": "synthetic-hash", "change_summary": "Synthetic record check",
                         "recorded_dates": [], "error": "Source unavailable" if source_status == "ERROR" else None}],
            "findings": ["The synthetic ownership record was checked."],
            "next_checks": ["Confirm whether the recorded owner still controls the property."],
            "change_summary": "Synthetic baseline, not a seller assertion."}


class ResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "pilot.sqlite")
        self.review = ReviewStore(self.path)
        self.store = ResearchStore(self.path)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, count=1):
        self.review.initialize()
        self.review.import_payload(pilot_payload(count), "operator")
        self.store.initialize()
        return self.review.list_cases()

    def count(self, table):
        with sqlite3.connect(self.path) as connection:
            return connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]

    def complete(self, *, now=None, **kwargs):
        claim = self.store.claim_next("test-worker", now=now or self.now)
        data = bundle(claim, **kwargs)
        saved = self.store.finish(claim["run_id"], claim["lease_token"], data, now=now or self.now)
        return claim, data, saved

    def test_reads_and_constructor_never_create_storage(self):
        self.assertFalse(self.store.ready())
        self.assertFalse(self.store.review_ready())
        self.assertFalse(self.store.status()["available"])
        self.assertIsNone(self.store.latest("missing"))
        self.assertEqual(self.store.history("missing"), [])
        self.assertEqual(self.store.export_payload(), {})
        self.assertFalse(Path(self.path).exists())
        with self.assertRaises(ValueError):
            self.store.initialize()
        self.assertFalse(Path(self.path).exists())

    def test_initialize_only_adds_isolated_tables_preserving_workspace(self):
        self.review.initialize()
        self.review.import_payload(pilot_payload(), "operator")
        before = self.review.export_payload()
        before.pop("generated_at")
        self.store.initialize()
        self.store.initialize()
        after = self.review.export_payload()
        after.pop("generated_at")
        self.assertEqual(before, after)
        self.assertTrue(self.store.status()["enabled"])
        with sqlite3.connect(self.path) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        added = tables - {"pmi_review_imports", "pmi_review_case_versions", "pmi_review_cases", "pmi_review_events", "pmi_ai_review_records"}
        self.assertTrue(all(name.startswith("pmi_research_") for name in added))
        self.assertEqual(len(added), 5)

    def test_finish_preserves_stage_notes_analysis_feedback_and_case_versions(self):
        case = self.load()[0]
        self.review.set_state(case["case_id"], "WAITING", "Operator's real working note", "operator", "note-1")
        before = self.review.case(case["case_id"])
        counts = (self.count("pmi_review_case_versions"), self.count("pmi_ai_review_records"))
        claim, data, saved = self.complete()
        after = self.review.case(case["case_id"])
        for key in ("state", "notes", "analysis", "evidence", "baseline", "pilot", "seller_intent"):
            self.assertEqual(before[key], after[key])
        self.assertEqual(counts, (self.count("pmi_review_case_versions"), self.count("pmi_ai_review_records")))
        events = [event for event in after["history"] if event["kind"] == "RESEARCH"]
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["data"]["seller_intent_inferred"])

    def test_duplicate_completion_and_content_are_idempotent(self):
        case = self.load()[0]
        claim, data, saved = self.complete()
        self.assertEqual(saved["new_snapshots"], 1)
        replay = self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now + timedelta(minutes=20))
        self.assertTrue(replay["already_finished"])
        self.assertEqual(self.count("pmi_research_runs"), 1)
        claim2, _, saved2 = self.complete(now=self.now + timedelta(days=1))
        self.assertEqual(saved2["new_snapshots"], 0)
        self.assertEqual(self.count("pmi_research_snapshots"), 1)
        self.assertEqual(self.count("pmi_research_runs"), 2)
        self.assertIn("owner", claim2["previous_sources"])
        self.assertEqual(len([event for event in self.review.history(case["case_id"]) if event["kind"] == "RESEARCH"]), 2)

    def test_same_objectid_changed_owner_creates_distinct_retained_snapshot(self):
        case = self.load()[0]
        self.complete(owner="First recorded owner")
        self.complete(now=self.now + timedelta(days=1), owner="Changed recorded owner")
        self.assertEqual(self.count("pmi_research_snapshots"), 2)
        self.assertEqual(self.store.latest(case["case_id"])["retained_sources"][0]["records"][0]["OWNERNME1"], "Changed recorded owner")

    def test_error_and_partial_sources_keep_last_good_distinct_from_current_status(self):
        case = self.load()[0]
        self.complete(owner="Last good owner")
        self.complete(now=self.now + timedelta(days=1), status="PARTIAL", source_status="ERROR")
        latest = self.store.latest(case["case_id"])
        self.assertEqual(latest["status"], "PARTIAL")
        self.assertEqual(latest["sources"][0]["status"], "ERROR")
        self.assertEqual(latest["retained_sources"][0]["status"], "SUCCESS")
        self.assertEqual(latest["retained_sources"][0]["records"][0]["OWNERNME1"], "Last good owner")
        self.assertEqual(self.count("pmi_research_snapshots"), 1)

    def test_complete_empty_is_a_successful_absence_not_a_source_failure(self):
        case = self.load()[0]
        self.complete()
        self.complete(now=self.now + timedelta(days=1), source_status="EMPTY")
        retained = self.store.latest(case["case_id"])["retained_sources"][0]
        self.assertEqual(retained["status"], "EMPTY")
        self.assertEqual(retained["records"], [])
        self.assertEqual(self.count("pmi_research_snapshots"), 2)

    def test_success_daily_and_failure_six_hour_retry(self):
        self.load()
        self.complete()
        self.assertIsNone(self.store.claim_next("before-daily", now=self.now + timedelta(hours=23)))
        claim = self.store.claim_next("daily", now=self.now + timedelta(hours=24))
        self.store.finish(claim["run_id"], claim["lease_token"], bundle(claim, status="ERROR", source_status="ERROR"), now=self.now + timedelta(hours=24))
        self.assertIsNone(self.store.claim_next("before-retry", now=self.now + timedelta(hours=29)))
        self.assertIsNotNone(self.store.claim_next("retry", now=self.now + timedelta(hours=30)))

    def test_pause_persists_across_store_and_initialize_and_blocks_acquisition(self):
        self.load()
        self.store.set_enabled(False, "operator")
        other = ResearchStore(self.path)
        other.initialize()
        self.assertFalse(other.status()["enabled"])
        self.assertEqual(other.request_run(None, "operator")["request_count"], 1)
        self.assertIsNone(other.claim_next("paused-worker"))
        other.set_enabled(True, "operator")
        self.assertIsNotNone(other.claim_next("resumed-worker"))

    def test_manual_cooldown_and_queue_do_not_fetch(self):
        case = self.load()[0]
        self.complete()
        self.assertEqual(self.store.request_run(case["case_id"], "operator"), {"request_count": 0, "cooldown": True, "cooldown_count": 1})
        with patch("pmi_research_store._moment", wraps=lambda value=None: self.now + timedelta(minutes=6) if value is None else datetime.fromisoformat(value) if isinstance(value, str) else value):
            result = self.store.request_run(case["case_id"], "operator")
        self.assertEqual(result["request_count"], 1)
        self.assertEqual(self.count("pmi_research_runs"), 1)
        self.assertIsNotNone(self.store.claim_next("manual-worker", now=self.now + timedelta(minutes=6)))

    def test_only_current_five_pilot_properties_are_claimed(self):
        cases = self.load(7)
        pilot_ids = {case["case_id"] for case in cases if case["pilot"]}
        picked = set()
        for _ in range(5):
            claim, _, _ = self.complete()
            picked.add(claim["case"]["case_id"])
        self.assertEqual(picked, pilot_ids)
        self.assertIsNone(self.store.claim_next("done-worker", now=self.now))
        excluded = next(case for case in cases if not case["pilot"])
        with self.assertRaises(ValueError):
            self.store.request_run(excluded["case_id"], "operator")

    def test_removed_and_set_aside_pilot_members_are_not_claimed(self):
        cases = self.load(3)
        self.review.set_pilot(cases[0]["case_id"], False, "operator", "remove-1")
        self.review.set_state(cases[1]["case_id"], "DISMISSED", "Set aside", "operator", "dismiss-1")
        claim = self.store.claim_next("worker", now=self.now)
        self.assertEqual(claim["case"]["case_id"], cases[2]["case_id"])
        self.assertEqual(self.store.status()["pilot_count"], 1)
        with self.assertRaises(ValueError):
            self.store.request_run(cases[1]["case_id"], "operator")

    def test_concurrent_store_claims_allow_only_one_global_lease(self):
        self.load(5)
        with ThreadPoolExecutor(max_workers=8) as executor:
            claims = list(executor.map(lambda index: ResearchStore(self.path).claim_next("worker-" + str(index), now=self.now), range(8)))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        self.assertEqual(self.count("pmi_research_runs"), 1)

    def test_restart_expiry_marks_interrupted_and_fences_old_worker(self):
        self.load(2)
        stale = self.store.claim_next("old-worker", now=self.now)
        replacement = ResearchStore(self.path).claim_next("new-worker", now=self.now + timedelta(seconds=181))
        self.assertIsNotNone(replacement)
        self.assertNotEqual(stale["case"]["case_id"], replacement["case"]["case_id"])
        with self.assertRaises(ValueError):
            self.store.finish(stale["run_id"], stale["lease_token"], bundle(stale), now=self.now + timedelta(seconds=182))
        self.assertEqual(self.count("pmi_research_snapshots"), 0)
        self.assertEqual(self.store.history(stale["case"]["case_id"])[0]["status"], "INTERRUPTED")

    def test_expiry_alone_rejects_finish_without_a_replacement(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        with self.assertRaises(ValueError):
            self.store.finish(claim["run_id"], claim["lease_token"], bundle(claim), now=self.now + timedelta(seconds=180))
        self.assertEqual(self.count("pmi_research_snapshots"), 0)

    def test_token_and_case_identity_fail_before_any_evidence_write(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        for change in ({"case_id": "another-case"}, {"parcel_id": "another-parcel"}):
            data = bundle(claim)
            data.update(change)
            with self.assertRaises(ValueError):
                self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now)
        with self.assertRaises(ValueError):
            self.store.finish(claim["run_id"], "forged-token", bundle(claim), now=self.now)
        self.assertEqual(self.count("pmi_research_snapshots"), 0)
        self.assertEqual(len([event for event in self.review.history(claim["case"]["case_id"]) if event["kind"] == "RESEARCH"]), 0)

    def test_failed_completion_rolls_back_all_snapshots_history_and_schedule(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        with patch.object(self.store, "_append", side_effect=RuntimeError("Synthetic audit write failure")):
            with self.assertRaises(RuntimeError):
                self.store.finish(claim["run_id"], claim["lease_token"], bundle(claim), now=self.now)
        self.assertEqual(self.count("pmi_research_snapshots"), 0)
        self.assertEqual(self.count("pmi_research_sources"), 0)
        self.assertEqual(self.store.latest(claim["case"]["case_id"])["status"], "RUNNING")
        self.assertIsNone(self.store.claim_next("another-worker", now=self.now))

    def test_research_reads_leave_database_unchanged(self):
        case = self.load()[0]
        self.complete()
        before = Path(self.path).read_bytes()
        other = ResearchStore(self.path)
        other.ready()
        other.status()
        other.latest(case["case_id"])
        other.history(case["case_id"])
        other.export_payload()
        self.assertEqual(before, Path(self.path).read_bytes())

    def test_incomplete_claimed_success_is_not_saved_as_good(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        data = bundle(claim)
        data["sources"][0]["complete"] = False
        with self.assertRaises(ValueError):
            self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now)
        self.assertEqual(self.count("pmi_research_sources"), 0)

    def test_overall_success_cannot_hide_failed_source_or_no_checks(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        failed = bundle(claim, source_status="ERROR")
        empty = bundle(claim)
        empty["sources"] = []
        for data in (failed, empty):
            with self.assertRaises(ValueError):
                self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now)
        self.assertEqual(self.count("pmi_research_sources"), 0)

    def test_successful_sources_require_reconciled_record_counts_and_checked_dates(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        for field, value in (("expected_count", 2), ("observed_at", None), ("records", ["unstructured-record"])):
            data = bundle(claim)
            data["sources"][0][field] = value
            with self.assertRaises(ValueError):
                self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now)
        self.assertEqual(self.count("pmi_research_sources"), 0)

    def test_wrong_row_parcel_rejected_for_success_and_partial_failure(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        for status in ("SUCCESS", "PARTIAL"):
            data = bundle(claim, status=status)
            data["sources"][0]["records"][0]["PARCELID"] = "0900000000000009999"
            if status == "PARTIAL":
                data["sources"][0].update({"status": "INCOMPLETE", "complete": False})
            with self.assertRaises(ValueError):
                self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now)
        self.assertEqual(self.count("pmi_research_snapshots"), 0)
        self.assertEqual(self.count("pmi_research_sources"), 0)

    def test_record_limit_matches_collector_100_row_boundary(self):
        self.load()
        claim = self.store.claim_next("worker", now=self.now)
        data = bundle(claim)
        data["sources"][0]["records"] = [{"OBJECTID": index, "PARCELID": claim["case"]["parcel_id"]} for index in range(101)]
        data["sources"][0]["expected_count"] = 101
        with self.assertRaises(ValueError):
            self.store.finish(claim["run_id"], claim["lease_token"], data, now=self.now)
        self.assertEqual(self.count("pmi_research_snapshots"), 0)

    def test_private_research_backup_includes_history_snapshots_pointers_not_lease_secrets(self):
        case = self.load()[0]
        first, _, _ = self.complete(owner="First recorded owner")
        self.complete(now=self.now + timedelta(days=1), owner="Changed recorded owner")
        self.store.set_enabled(False, "operator")
        data = ResearchStore(self.path).export_payload()
        self.assertFalse(data["enabled"])
        self.assertEqual(len(data["runs"]), 2)
        self.assertEqual(len(data["source_snapshots"]), 2)
        self.assertEqual(len(data["source_pointers"]), 1)
        self.assertEqual(len(data["schedules"]), 1)
        self.assertEqual(data["source_pointers"][0]["source"]["records"][0]["OWNERNME1"], "Changed recorded owner")
        self.assertEqual(data["source_pointers"][0]["case_id"], case["case_id"])
        self.assertNotIn(first["lease_token"], str(data))
        self.assertNotIn("lease_token", str(data))
        self.assertNotIn(self.path, str(data))


if __name__ == "__main__":
    unittest.main()
