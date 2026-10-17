"""Synthetic proposal tests through the existing persistence and daily scheduler."""
import copy
from datetime import date, datetime, timedelta, timezone
import json
import os
import tempfile
import unittest

from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from pmi_research_worker import run_once
from pmi_case_sources import _url
from test_research_store import pilot_payload
from test_property_selection_feedback import SelectionLoopChecks
from experiments.pmi_feedback_loop_proposal import reassess, compare, persist_projection

DAY = date(2026, 10, 17)

class LoopChecks:
    setUp_base = SelectionLoopChecks.setUp
    tearDown = SelectionLoopChecks.tearDown
    token = SelectionLoopChecks.token
    page = SelectionLoopChecks.page
    rows = SelectionLoopChecks.rows
    data = SelectionLoopChecks.data

    def setUp(self):
        self.setUp_base()
        self.store.import_payload(pilot_payload(8), "SYNTHETIC")
        self.ids = [c["case_id"] for c in self.store.list_cases() if c["parcel_id"].startswith("0900")]
        self.seed = self.ids[0]
        for n in range(5):
            self.store.set_state(self.seed, "COMPLETE", "SYNTHETIC existing note " + str(n), "operator", "seednote-" + str(n))
        # All matches use existing explicitly verified typed evidence, never note parsing.
        for cid in self.ids[:3]:
            self.fact(cid, "property_form", "DETACHED")
            self.fact(cid, "occupancy_status", "VACANT")
        self.fact(self.ids[3], "occupancy_status", "VACANT")  # vacancy alone must fail
        self.fact(self.ids[4], "property_form", "DETACHED", verified=False)
        self.fact(self.ids[4], "occupancy_status", "VACANT")
        self.fact(self.ids[5], "property_form", "ATTACHED")
        self.fact(self.ids[5], "occupancy_status", "VACANT")
        self.fact(self.ids[6], "property_form", "DETACHED", observed="2020-01-01")
        self.fact(self.ids[6], "occupancy_status", "VACANT", observed="2020-01-01")
        self.fact(self.ids[7], "property_form", "DETACHED")
        self.fact(self.ids[7], "occupancy_status", "VACANT")
        self.review(self.ids[7], "FALSE_POSITIVE", "negative-candidate")

    def fact(self, cid, field, value, verified=True, observed="2026-10-17"):
        self.store.add_evidence(cid, {"kind": "FACT", "field": field, "value": value,
            "observed_at": observed, "source_record_id": "SYNTHETIC-" + field,
            "verified": verified, "current": True}, "SYNTHETIC operator",
            cid + "-" + field + "-" + str(value))

    def review(self, cid, outcome="USEFUL_INVESTIGATION", event="seed-review", verified=True):
        case = self.store.case(cid)
        self.store.review(cid, {"selection_version_id": case["selection_version_id"],
            "selection_reason_id": case["selection_reason_ids"][0], "outcome": outcome,
            "method": "OPERATOR_REVIEW", "detail": "SYNTHETIC chosen finding; not Cece's conclusion.",
            "verified": verified}, "SYNTHETIC operator", event)

    def inventory(self):
        return [self.store.case(cid) for cid in self.ids]

    def sources(self, cid, owner="SYNTHETIC owner A"):
        c = self.store.case(cid)
        return [{"source_key": "owner", "status": "SUCCESS", "complete": True,
            "expected_count": 1, "query_url": _url("TaxParcelOwner", c["parcel_id"], outFields="*", returnGeometry="false"),
            "observed_at": "2026-10-17T00:00:00+00:00", "recorded_dates": [],
            "records": [{"OBJECTID": 1, "PARCELID": c["parcel_id"], "OWNERNAME": owner}]}]

    def test_review_changes_reassessment_and_links_two_comparisons(self):
        c = self.store.case(self.seed)
        before = reassess(c, [], as_of=DAY)
        self.assertEqual(before["assessment"], "AWAITING_EXPLICIT_REVIEW")
        self.assertEqual(compare(c, self.inventory(), as_of=DAY)["candidates"], [])
        self.review(self.seed)
        after_case = self.store.case(self.seed)
        after = reassess(after_case, [], as_of=DAY)
        matches = compare(after_case, self.inventory(), as_of=DAY)
        self.assertEqual(after["assessment"], "REVIEW_SUPPORTS_PROPERTY_RESEARCH")
        self.assertEqual(after["review_reference"]["event_id"], "seed-review")
        self.assertEqual({x["case_id"] for x in matches["candidates"]}, set(self.ids[1:3]))
        self.assertEqual(len(matches["excluded"]), 5)
        for item in matches["candidates"]:
            self.assertEqual(item["informed_by_review"], "seed-review")
            self.assertEqual(item["seller_intent"], "UNKNOWN")
            self.assertFalse(item["contact_authorized"])
            self.assertTrue(item["missing_information"])
        self.assertEqual(c["notes"], after_case["notes"])
        self.assertEqual(c["baseline"], after_case["baseline"])
        self.assertEqual(self.store.learning_report()["counts"]["review_events"], 2)
        persist_projection(self.store, after)
        reopened = ReviewStore(self.store.dsn)
        self.assertEqual(reopened.case(self.seed)["notes"], c["notes"])
        with reopened._session() as conn:
            saved = reopened._sql(conn, "SELECT data_json FROM pmi_ai_review_records WHERE record_key=?",
                ("property_projection:" + after["projection_id"],)).fetchone()
        self.assertEqual(json.loads(saved[0])["review_reference"]["event_id"], "seed-review")
        print("LOOP_PROPOSAL_DEMO " + json.dumps({"synthetic": True, "before": before["assessment"],
            "after": after["assessment"], "candidates": matches, "notes_retained": len(c["notes"])}))

    def test_negative_review_and_unverified_review_cannot_seed_matches(self):
        self.review(self.seed, verified=False)
        self.assertEqual(reassess(self.store.case(self.seed), [], as_of=DAY)["assessment"], "AWAITING_EXPLICIT_REVIEW")
        self.assertEqual(compare(self.store.case(self.seed), self.inventory(), as_of=DAY)["candidates"], [])
        self.review(self.seed, "FALSE_POSITIVE", "negative-seed")
        self.assertEqual(reassess(self.store.case(self.seed), [], as_of=DAY)["assessment"], "REVIEW_CONTRADICTS_ORIGINAL")
        self.assertEqual(compare(self.store.case(self.seed), self.inventory(), as_of=DAY)["candidates"], [])

    def test_missing_dates_and_vacation_vacancy_tension_are_not_current_facts(self):
        c = copy.deepcopy(self.store.case(self.seed))
        for event in c["evidence"]:
            if event["data"]["field"] == "occupancy_status":
                event["data"]["observed_at"] = ""
        c["evidence"].append({"event_id": "undated-vacation", "data": {
            "kind": "FACT", "field": "occupancy_status", "value": "VACATION_HOME",
            "observed_at": "", "verified": False, "current": True, "source_record_id": "SYNTHETIC-old-note"}})
        out = reassess(c, self.sources(self.seed), as_of=DAY)
        self.assertNotIn("occupancy_status", out["usable_explicit_facts"])
        self.assertGreaterEqual(len(out["excluded_observations"]), 2)
        self.assertFalse(out["source_evidence"][0]["current_occupancy_established"])
        # If both claims are explicitly current, preserve the tension rather than choose newest.
        for event in c["evidence"]:
            if event["data"]["field"] == "occupancy_status":
                event["data"].update(observed_at="2026-10-17", verified=True)
        out = reassess(c, [], as_of=DAY)
        self.assertEqual(out["contradictions"][0]["field"], "occupancy_status")
        self.assertNotIn("occupancy_status", out["usable_explicit_facts"])

    def test_source_identity_completeness_and_unchanged_records(self):
        c = self.store.case(self.seed)
        a = reassess(c, self.sources(self.seed), as_of=DAY)
        persist_projection(self.store, a)
        count = len(self.rows("pmi_ai_review_records"))
        s = self.sources(self.seed); s[0]["observed_at"] = "2026-10-18T00:00:00+00:00"
        b = reassess(c, s, previous=a, as_of=DAY)
        self.assertEqual(a["projection_id"], b["projection_id"])
        persist_projection(self.store, b)
        self.assertEqual(count, len(self.rows("pmi_ai_review_records")))
        s[0]["records"][0]["PARCELID"] = "OTHER-PARCEL"
        bad = reassess(c, s, as_of=DAY)
        self.assertEqual(bad["source_evidence"], [])
        self.assertTrue(bad["rejected_sources"])
        s = self.sources(self.seed); s[0]["complete"] = False
        self.assertEqual(reassess(c, s, as_of=DAY)["source_evidence"], [])

    def test_real_scheduler_runs_five_pilots_then_changed_record_reassesses(self):
        self.review(self.seed)
        clock = datetime(2026, 10, 17, tzinfo=timezone.utc)
        review_store = self.store
        assessments = {}
        outer = self

        class ProposalStore(ResearchStore):
            # Test-only adapter. Existing production finish/run_once are unchanged.
            def claim_next(self, worker_id, now=None):
                return super().claim_next(worker_id, now=clock)
            def finish(self, run_id, lease_token, bundle, now=None):
                result = super().finish(run_id, lease_token, bundle, now=clock)
                cid = bundle["case_id"]
                with self._session() as conn:
                    sources = self._retained(conn, cid)
                p = reassess(review_store.case(cid), sources, previous=assessments.get(cid), as_of=clock.date())
                persist_projection(review_store, p)
                assessments[cid] = p
                return result

        r = ProposalStore(self.store.dsn)
        r.initialize()
        # Use exactly the five intended fixtures, without expanding research beyond five.
        for c in self.store.list_cases():
            if c["pilot"]: self.store.set_pilot(c["case_id"], False, "test", "remove-" + c["case_id"])
        for cid in self.ids[:5]:
            self.store.set_pilot(cid, True, "test", "pilot-" + cid)
        owner = "SYNTHETIC owner A"
        collected = []
        def collector(c, previous):
            collected.append(c["case_id"])
            sources = outer.sources(c["case_id"], owner)
            sources[0]["observed_at"] = clock.isoformat()
            return {"case_id": c["case_id"], "parcel_id": c["parcel_id"],
                "observed_at": clock.isoformat(), "status": "SUCCESS",
                "sources": sources, "findings": [],
                "next_checks": ["Verify current authority independently."], "change_summary": "SYNTHETIC test source."}
        for _ in range(5): self.assertEqual(run_once(r, collector=collector)["status"], "SUCCESS")
        self.assertEqual(set(collected), set(self.ids[:5]))
        first = copy.deepcopy(assessments)
        self.assertEqual(run_once(r, collector=collector)["status"], "IDLE")
        clock += timedelta(hours=23)
        self.assertEqual(run_once(r, collector=collector)["status"], "IDLE")
        before_rows = len([x for x in self.rows("pmi_ai_review_records") if x[1] == "PROPERTY_FEEDBACK_PROJECTION"])
        clock += timedelta(hours=1)
        for _ in range(5): run_once(r, collector=collector)
        self.assertEqual(len([x for x in self.rows("pmi_ai_review_records") if x[1] == "PROPERTY_FEEDBACK_PROJECTION"]), before_rows)
        owner = "SYNTHETIC owner B"
        clock += timedelta(days=1)
        for _ in range(5): run_once(r, collector=collector)
        changed = assessments[self.seed]
        self.assertTrue(changed["needs_source_recheck"])
        delta = changed["source_changes"][0]["fields"]["OWNERNAME"]
        self.assertEqual(delta, {"before": "SYNTHETIC owner A", "after": "SYNTHETIC owner B"})
        self.assertEqual(changed["review_reference"]["event_id"], "seed-review")
        matches = compare(self.store.case(self.seed), self.inventory(), as_of=clock.date(), assessments=assessments)
        self.assertTrue(matches["candidates"][0]["daily_source_changes"])
        self.assertEqual(changed["seller_intent"], "UNKNOWN")
        self.assertEqual(len(self.store.case(self.seed)["notes"]), 5)
        with r._session() as conn:
            runs = r._sql(conn, "SELECT case_id,started_at,completed_at,status FROM pmi_research_runs ORDER BY started_at,case_id").fetchall()
        self.assertEqual(len(runs), 15)
        print("LOOP_SCHEDULE_PROOF " + json.dumps({"synthetic_clock": True, "run_records": runs,
            "before_source": first[self.seed]["source_evidence"][0]["records"],
            "after_source": changed["source_evidence"][0]["records"], "analysis_delta": delta,
            "unchanged_day_projection_count": before_rows, "changed_day_recheck": changed["needs_source_recheck"]}))

class LoopSQLiteTests(LoopChecks, unittest.TestCase):
    postgres = False

@unittest.skipUnless(os.environ.get("PMI_TEST_POSTGRES_DSN"), "Disposable PostgreSQL required")
class LoopPostgresTests(LoopChecks, unittest.TestCase):
    postgres = True

if __name__ == "__main__":
    unittest.main()
