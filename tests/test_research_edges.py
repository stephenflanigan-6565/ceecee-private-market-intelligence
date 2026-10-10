"""Independent high-risk research edges; synthetic records, no external calls."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore, LEASE_SECONDS
from test_review_store import payload, fact


def synthetic_payload(count=1):
    data = payload(count)
    for index, row in enumerate(data["profiles"]):
        row["parcel_id"] = "090000100010000100" + str(index + 1)
    return data


def result(claim, now, *, owner="Synthetic initial owner", status="SUCCESS"):
    source_status = "SUCCESS" if status == "SUCCESS" else "INCOMPLETE"
    return {
        "case_id": claim["case"]["case_id"],
        "parcel_id": claim["case"]["parcel_id"],
        "observed_at": now.isoformat(), "status": status,
        "sources": [{
            "source_key": "owner", "source_name": "Synthetic official owner source",
            "query_url": "https://synthetic.invalid/owner", "citation": "SYNTHETIC",
            "observed_at": now.isoformat(), "status": source_status,
            "complete": status == "SUCCESS", "expected_count": 1,
            "records": [{"OBJECTID": 7, "PARCELID": claim["case"]["parcel_id"],
                         "OWNERNAME": owner}],
            "recorded_dates": [], "change_summary": "Synthetic result."}],
        "findings": ["Synthetic ownership record only; seller plans remain unknown."],
        "next_checks": ["Verify an actual reason for selling."],
        "change_summary": "Synthetic source check."}


class IndependentResearchStoreEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "edge.sqlite")
        self.review = ReviewStore(self.path)
        self.review.initialize()
        self.review.import_payload(synthetic_payload(2), "synthetic-operator")
        self.store = ResearchStore(self.path)
        self.store.initialize()
        self.now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, sql, parameters=()):
        with sqlite3.connect(self.path) as connection:
            return connection.execute(sql, parameters).fetchall()

    def test_changed_owner_on_same_objectid_is_new_immutable_source_not_requalification(self):
        # Use one enrolled case so due scheduling cannot select a different one.
        one, two = self.review.list_cases()
        self.review.set_pilot(two["case_id"], False, "operator", "remove-second")
        self.review.set_state(one["case_id"], "WAITING", "Synthetic working note",
                              "operator", "working-note")
        # Install an actual verified negative review, rather than merely
        # asserting that a case with no feedback remains unchanged.
        self.review.add_evidence(one["case_id"], fact(), "operator", "project-fact")
        qualified = self.review.add_evidence(one["case_id"], fact("current_use", "VACANT"),
                                             "operator", "occupancy-fact")
        hypothesis = qualified["analysis"]["hypotheses"][0]
        self.review.review(one["case_id"], {
            "analysis_id": qualified["analysis_id"],
            "hypothesis_id": hypothesis["hypothesis_id"], "outcome": "FALSE_POSITIVE",
            "method": "OPERATOR_REVIEW", "verified": True,
            "detail": "Synthetic verified review disproves this explanation."},
            "operator", "negative-review")
        before = self.review.case(one["case_id"])
        original_versions = self.rows("SELECT version_id FROM pmi_review_case_versions")
        original_memory = self.rows("SELECT record_key FROM pmi_ai_review_records ORDER BY record_key")
        first = self.store.claim_next("worker-one", self.now)
        self.store.finish(first["run_id"], first["lease_token"], result(first, self.now),
                          self.now + timedelta(seconds=1))
        second_time = self.now + timedelta(hours=25)
        second = self.store.claim_next("worker-two", second_time)
        self.assertEqual(second["previous_sources"]["owner"]["records"][0]["OWNERNAME"],
                         "Synthetic initial owner")
        self.store.finish(second["run_id"], second["lease_token"],
                          result(second, second_time, owner="Synthetic changed owner"),
                          second_time + timedelta(seconds=1))
        snapshots = self.rows("SELECT source_json FROM pmi_research_snapshots")
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(self.store.latest(one["case_id"])["retained_sources"][0]
                         ["records"][0]["OWNERNAME"], "Synthetic changed owner")
        after = self.review.case(one["case_id"])
        for key in ("analysis_id", "analysis", "state", "pilot", "notes", "evidence", "seller_intent"):
            self.assertEqual(before[key], after[key], key)
        self.assertEqual(original_versions, self.rows("SELECT version_id FROM pmi_review_case_versions"))
        self.assertEqual(original_memory,
                         self.rows("SELECT record_key FROM pmi_ai_review_records ORDER BY record_key"))
        # A fresh check of identical content is still a run, not a third snapshot.
        third_time = second_time + timedelta(hours=25)
        third = self.store.claim_next("worker-three", third_time)
        self.store.finish(third["run_id"], third["lease_token"],
                          result(third, third_time, owner="Synthetic changed owner"),
                          third_time + timedelta(seconds=1))
        self.assertEqual(len(self.rows("SELECT snapshot_id FROM pmi_research_snapshots")), 2)
        self.assertEqual(len(self.rows("SELECT run_id FROM pmi_research_runs")), 3)

    def test_failure_after_snapshot_and_pointer_updates_rolls_back_whole_completion(self):
        claim = self.store.claim_next("worker", self.now)
        data = result(claim, self.now)
        with patch.object(self.store, "_append", side_effect=RuntimeError("synthetic late failure")):
            with self.assertRaises(RuntimeError):
                self.store.finish(claim["run_id"], claim["lease_token"], data, self.now)
        self.assertEqual(self.rows("SELECT snapshot_id FROM pmi_research_snapshots"), [])
        self.assertEqual(self.rows("SELECT snapshot_id FROM pmi_research_sources"), [])
        self.assertEqual(self.rows("SELECT status,bundle_json FROM pmi_research_runs"), [("RUNNING", None)])
        self.assertEqual(self.rows("SELECT lease_run_id FROM pmi_research_control"), [(claim["run_id"],)])
        self.store.finish(claim["run_id"], claim["lease_token"], data, self.now)
        self.assertEqual(len(self.rows("SELECT event_id FROM pmi_review_events WHERE kind='RESEARCH'")), 1)

    def test_missing_or_naive_check_timestamp_cannot_become_successful_evidence(self):
        claim = self.store.claim_next("worker", self.now)
        valid = result(claim, self.now)
        for level in ("bundle", "source"):
            for timestamp in (None, "2026-10-10T12:00:00", "not-a-date"):
                with self.subTest(level=level, timestamp=timestamp):
                    data = copy.deepcopy(valid)
                    target = data if level == "bundle" else data["sources"][0]
                    if timestamp is None:
                        target.pop("observed_at")
                    else:
                        target["observed_at"] = timestamp
                    with self.assertRaises(ValueError):
                        self.store.finish(claim["run_id"], claim["lease_token"], data, self.now)
        self.assertEqual(self.rows("SELECT snapshot_id FROM pmi_research_snapshots"), [])
        self.assertEqual(self.rows("SELECT status FROM pmi_research_runs"), [("RUNNING",)])

    def test_expired_worker_cannot_complete_during_persistent_pause_or_after_takeover(self):
        old = self.store.claim_next("old-worker", self.now)
        self.store.set_enabled(False, "operator")
        restarted = ResearchStore(self.path)
        restarted.initialize()
        expired_at = self.now + timedelta(seconds=LEASE_SECONDS + 1)
        self.assertIsNone(restarted.claim_next("restarted-worker", expired_at))
        self.assertFalse(restarted.status()["enabled"])
        self.assertEqual(self.rows("SELECT status FROM pmi_research_runs"), [("INTERRUPTED",)])
        with self.assertRaises(ValueError):
            self.store.finish(old["run_id"], old["lease_token"], result(old, expired_at), expired_at)
        restarted.set_enabled(True, "operator")
        replacement = restarted.claim_next("new-worker", expired_at)
        self.assertIsNotNone(replacement)
        self.assertNotEqual(old["run_id"], replacement["run_id"])
        with self.assertRaises(ValueError):
            self.store.finish(old["run_id"], old["lease_token"], result(old, expired_at), expired_at)
        self.assertEqual(self.rows("SELECT lease_run_id FROM pmi_research_control"),
                         [(replacement["run_id"],)])
        self.assertEqual(self.rows("SELECT snapshot_id FROM pmi_research_snapshots"), [])

    def test_partial_owner_response_keeps_prior_good_owner_and_exact_case_fencing(self):
        one, two = self.review.list_cases()
        self.review.set_pilot(two["case_id"], False, "operator", "remove-second")
        first = self.store.claim_next("first-worker", self.now)
        self.store.finish(first["run_id"], first["lease_token"], result(first, self.now), self.now)
        later = self.now + timedelta(hours=25)
        second = self.store.claim_next("second-worker", later)
        bad = result(second, later, owner="Unreconciled owner", status="PARTIAL")
        for key, wrong in (("case_id", two["case_id"]), ("parcel_id", two["parcel_id"])):
            crossed = {**bad, key: wrong}
            with self.assertRaises(ValueError):
                self.store.finish(second["run_id"], second["lease_token"], crossed, later)
        self.store.finish(second["run_id"], second["lease_token"], bad, later)
        saved = self.store.latest(one["case_id"])
        self.assertEqual(saved["sources"][0]["status"], "INCOMPLETE")
        self.assertEqual(saved["retained_sources"][0]["records"][0]["OWNERNAME"],
                         "Synthetic initial owner")
        self.assertEqual(len(self.rows("SELECT snapshot_id FROM pmi_research_snapshots")), 1)

    def test_research_reads_are_byte_preserving_and_do_not_initialize_missing_database(self):
        absent = str(Path(self.tmp.name) / "not-created.sqlite")
        missing = ResearchStore(absent)
        self.assertFalse(missing.ready())
        self.assertFalse(missing.status()["available"])
        self.assertIsNone(missing.latest("unknown"))
        self.assertEqual(missing.history("unknown"), [])
        self.assertFalse(Path(absent).exists())
        claim = self.store.claim_next("worker", self.now)
        self.store.finish(claim["run_id"], claim["lease_token"], result(claim, self.now), self.now)
        before = Path(self.path).read_bytes()
        self.store.status()
        self.store.latest(claim["case"]["case_id"])
        self.store.history(claim["case"]["case_id"])
        self.assertEqual(before, Path(self.path).read_bytes())

    def test_collector_runs_without_holding_database_write_transaction(self):
        from pmi_research_worker import run_once

        touched = []
        def independent_writer(case, previous):
            # A separate connection can acquire a write transaction while the
            # collector runs. A scheduling transaction held around I/O fails.
            with sqlite3.connect(self.path, timeout=0.05) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("UPDATE pmi_research_control SET actor='independent-edge-writer'")
            touched.append(case["case_id"])
            claim = {"case": case}
            return result(claim, datetime.now(timezone.utc))

        outcome = run_once(self.store, collector=independent_writer, worker_id="edge-worker")
        self.assertEqual(outcome["status"], "SUCCESS")
        self.assertEqual(len(touched), 1)
        self.assertEqual(self.rows("SELECT actor FROM pmi_research_control"),
                         [("independent-edge-writer",)])

class IndependentResearchAcquisitionEdges(unittest.TestCase):
    def test_wall_deadline_preserves_earlier_source_and_starts_no_later_network_calls(self):
        import pmi_case_sources as sources
        instant = [100.0]
        calls = []
        parcel = "0905002000200013000"
        prior = {"owner": {"source_key": "owner", "status": "SUCCESS", "complete": True,
                            "observed_at": "2026-10-09T12:00:00+00:00",
                            "content_hash": "synthetic-prior-hash",
                            "records": [{"OBJECTID": 7, "PARCELID": parcel,
                                         "OWNERNAME": "Synthetic prior owner"}]}}

        def consume_budget(url, *, timeout):
            calls.append(url)
            self.assertLessEqual(timeout, sources.REQUEST_TIMEOUT)
            query = parse_qs(urlsplit(url).query)
            if "TaxParcelOwner/" in url:
                instant[0] += sources.CASE_DEADLINE_SECONDS + 1
            if query.get("returnCountOnly") == ["true"]:
                return {"count": 1}
            return {"features": [{"attributes": {"OBJECTID": 1, "PARCELID": parcel}}]}

        with patch.object(sources.time, "monotonic", side_effect=lambda: instant[0]):
            bundle = sources.collect_case({"case_id": "synthetic-case", "parcel_id": parcel},
                                          prior, fetch_json=consume_budget,
                                          observed_at="2026-10-10T12:00:00+00:00")
        self.assertEqual(bundle["status"], "PARTIAL")
        self.assertEqual(len(calls), 4)  # Parcel count/page/count, then owner count.
        self.assertTrue(bundle["sources"][0]["complete"])
        for source in bundle["sources"][1:]:
            self.assertFalse(source["complete"])
            self.assertIsNone(source["change_summary"]["removed"])
        self.assertEqual(bundle["sources"][1]["previous_successful_content_hash"],
                         "synthetic-prior-hash")
        self.assertFalse(any("TaxParcelTransfer" in url for url in calls))

    def test_slow_stream_is_stopped_by_wall_deadline_without_waiting_for_large_buffer(self):
        import pmi_case_sources as sources
        instant = [0.0]
        chunks = []
        url = sources._url("TaxParcelOwner", "0905002000200013000", returnCountOnly="true")

        class DripResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return url

            def read1(self, size):
                self.assert_size = size
                instant[0] += 3
                chunks.append(size)
                return b" "

            def read(self, size):
                raise AssertionError("A slow stream must use read1 instead of filling a buffer.")

        class Opener:
            def open(self, request, *, timeout):
                self.timeout = timeout
                return DripResponse()

        opener = Opener()
        with patch.object(sources.time, "monotonic", side_effect=lambda: instant[0]), \
             patch.object(sources.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(sources.SourceError):
                sources._fetch_official_json(url, timeout=8)
        self.assertEqual(opener.timeout, 8)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(instant[0], 9)

    def test_rounded_numeric_parcel_response_cannot_match_exact_text_identifier(self):
        import pmi_case_sources as sources
        parcel = "0905002000200013001"
        requested = []

        def rounded_owner(url, *, timeout):
            query = parse_qs(urlsplit(url).query)
            requested.append(query["where"][0])
            if query.get("returnCountOnly") == ["true"]:
                return {"count": 1}
            returned = float(parcel) if "TaxParcelOwner/" in url else parcel
            return {"features": [{"attributes": {"OBJECTID": 7, "PARCELID": returned}}]}

        bundle = sources.collect_case({"case_id": "synthetic-case", "parcel_id": parcel},
                                      fetch_json=rounded_owner,
                                      observed_at="2026-10-10T12:00:00+00:00")
        self.assertTrue(all(where == "PARCELID = '" + parcel + "'" for where in requested))
        self.assertEqual(bundle["status"], "PARTIAL")
        self.assertEqual(bundle["sources"][1]["status"], "ERROR")
        self.assertFalse(bundle["sources"][1]["complete"])
        self.assertEqual(bundle["sources"][1]["records"], [])


if __name__ == "__main__":
    unittest.main()
