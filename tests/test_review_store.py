"""Synthetic persistent-workspace tests, including rollback and safe reads."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pmi_review_store import ReviewStore


def payload(count=1, seller=False, closed=False):
    rows = []
    for index in range(count):
        if closed:
            routes = [{"route": "PROPERTY_FORM", "state": "EXPLAINED_ROUTE_CLOSED"}]
        elif seller:
            routes = [{"route": "PROJECT_CONTEXT", "state": "ACTIVE_RESEARCH_ROUTE", "actual_values": {"project_status": "COMPLETED", "current_use": "VACANT"}}]
        else:
            routes = [{"route": "LAND_PROPERTY_UTILIZATION", "state": "ACTIVE_CORROBORATED_RESEARCH_ROUTE", "noticed_because": "Synthetic corroborated opportunity", "supporting_evidence": ["SYNTHETIC_PROPERTY_CORROBORATION"], "actual_values": {"land_assessment": 900000, "improvement_assessment": 100000}, "next_question": "Verify the synthetic property constraint."}]
        rows.append({"parcel_id": "SYNTHETIC-" + str(index), "property_address": str(index + 1) + " SYNTHETIC TEST RD", "market_code": "SYNTHETIC", "owner_identity": {"names": []}, "why_pmi_noticed_it": routes})
    return {"status": "ok", "version": "FIND4", "profile_payload": {"complete": True, "total": count, "returned": count}, "profiles": rows}


def fact(field="project_status", value="COMPLETED", **kwargs):
    return {"field": field, "value": value, "observed_at": "2026-10-09", "source_record_id": "SYNTHETIC-SOURCE", "verified": True, "current": True, **kwargs}


def public(**kwargs):
    return {"kind": "PUBLIC_STATEMENT", "person_id": "synthetic-person", "display_name": "Synthetic owner", "quote": "Synthetic explicit property sale plan.", "statement_kind": "EXPLICIT_SELLING_PLAN", "source_record_id": "SYNTHETIC-STATEMENT", "identity_source_record_id": "SYNTHETIC-DEED", "identity_verified": True, "observed_at": "2026-10-09", "verified": True, "current": True, "property_specific": True, **kwargs}


class ReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "reviews.sqlite")
        self.store = ReviewStore("sqlite:///" + self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, data=None):
        self.store.initialize()
        self.store.import_payload(data or payload(), "authenticated-operator")
        return self.store.list_cases()[0]

    def count(self, table):
        with sqlite3.connect(self.path) as conn:
            return conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]

    def test_ctor_ready_and_missing_reads_do_not_create_file(self):
        self.assertFalse(self.store.ready())
        self.assertFalse(Path(self.path).exists())
        for action in (self.store.list_cases, self.store.export_payload, lambda: self.store.case("unknown"), lambda: self.store.history("unknown")):
            with self.assertRaises(ValueError):
                action()
        self.assertFalse(Path(self.path).exists())

    def test_requires_explicit_persistent_path(self):
        for dsn in ("", "relative.sqlite", ":memory:"):
            with self.assertRaises(ValueError):
                ReviewStore(dsn)

    def test_initialize_only_isolated_tables(self):
        self.store.initialize()
        self.store.initialize()
        with sqlite3.connect(self.path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"pmi_review_imports", "pmi_review_case_versions", "pmi_review_cases", "pmi_review_events", "pmi_ai_review_records"})

    def test_complete_cohort_retained_with_zero_seller_hypotheses(self):
        self.store.initialize()
        result = self.store.import_payload(payload(11), "operator")
        self.assertEqual(result["input_cases"], 11)
        self.assertEqual(result["cases_retained"], 11)
        self.assertEqual(result["seller_review_count"], 0)
        self.assertEqual(result["pilot_count"], 5)
        self.assertTrue(all(case["lane"] == "PROPERTY_RESEARCH" for case in self.store.list_cases()))
        self.assertEqual(sum(case["pilot"] for case in self.store.list_cases()), 5)
        self.assertEqual(result["external_calls"], 0)

    def test_truncated_and_failed_imports_leave_cohort_unchanged(self):
        self.load()
        before = self.store.export_payload()
        for change in ({"complete": False}, {"returned": 2}, {"total": 2}):
            data = payload()
            data["profile_payload"].update(change)
            with self.assertRaises(ValueError):
                self.store.import_payload(data, "operator")
        data = payload()
        data["status"] = "error"
        with self.assertRaises(ValueError):
            self.store.import_payload(data, "operator")
        self.assertEqual(self.store.export_payload()["cases"], before["cases"])
        self.assertEqual(self.count("pmi_review_imports"), 1)

    def test_bad_later_case_is_rejected_before_writes(self):
        self.load()
        data = payload(2)
        data["profiles"][1]["parcel_id"] = {}
        with self.assertRaises(ValueError):
            self.store.import_payload(data, "operator")
        self.assertEqual(self.count("pmi_review_cases"), 1)
        self.assertEqual(self.count("pmi_review_imports"), 1)

    def test_failure_in_second_case_rolls_back_all_import_and_memory(self):
        self.store.initialize()
        import pmi_review_store
        original = pmi_review_store.analyze
        calls = []
        def failing(packet, memory):
            calls.append(packet["case_id"])
            result = original(packet, memory)
            if len(calls) == 2:
                raise RuntimeError("synthetic transaction failure")
            return result
        with patch("pmi_review_store.analyze", failing):
            with self.assertRaises(RuntimeError):
                self.store.import_payload(payload(3), "operator")
        for table in ("pmi_review_cases", "pmi_review_imports", "pmi_ai_review_records", "pmi_review_case_versions", "pmi_review_events"):
            self.assertEqual(self.count(table), 0)

    def test_repeated_import_is_idempotent_and_preserves_state(self):
        case = self.load()
        self.store.set_state(case["case_id"], "WAITING", "Source return pending", "operator", "state-1")
        counts = (self.count("pmi_review_case_versions"), self.count("pmi_ai_review_records"), self.count("pmi_review_events"))
        result = self.store.import_payload(payload(), "second-operator")
        self.assertTrue(result["already_imported"])
        self.assertEqual(self.store.case(case["case_id"])["state"], "WAITING")
        self.assertEqual(counts, (self.count("pmi_review_case_versions"), self.count("pmi_ai_review_records"), self.count("pmi_review_events")))

    def test_all_read_methods_leave_database_bytes_unchanged(self):
        case = self.load(payload(seller=True))
        before = Path(self.path).read_bytes()
        with patch("pmi_review_store.analyze", side_effect=AssertionError("read must not analyze")):
            self.assertTrue(self.store.ready())
            self.store.list_cases()
            self.store.case(case["case_id"])
            self.store.history(case["case_id"])
            self.store.export_payload()
        self.assertEqual(Path(self.path).read_bytes(), before)

    def test_state_and_note_are_not_learning_feedback(self):
        case = self.load()
        memory = self.count("pmi_ai_review_records")
        self.store.set_state(case["case_id"], "COMPLETE", "I think they may sell", "trusted", "state-1")
        result = self.store.case(case["case_id"])
        self.assertEqual(result["state"], "COMPLETE")
        self.assertEqual(len(result["notes"]), 1)
        self.assertEqual(self.count("pmi_ai_review_records"), memory)
        self.assertEqual(result["analysis"]["seller_intent"], "UNKNOWN")

    def test_event_id_conflict_rejected_and_same_event_replay_safe(self):
        case = self.load()
        self.store.set_state(case["case_id"], "WAITING", "note", "trusted", "event-1")
        self.store.set_state(case["case_id"], "WAITING", "note", "trusted", "event-1")
        with self.assertRaises(ValueError):
            self.store.set_state(case["case_id"], "COMPLETE", "different", "trusted", "event-1")
        self.assertEqual(len([event for event in self.store.history(case["case_id"]) if event["kind"] == "STATE"]), 1)

    def test_captured_typed_facts_create_hypothesis_and_exact_citations(self):
        case = self.load()
        self.store.add_evidence(case["case_id"], fact(), "trusted", "source-1")
        result = self.store.add_evidence(case["case_id"], fact("current_use", "VACANT"), "trusted", "source-2")
        self.assertEqual(result["lane"], "SELLER_REVIEW")
        hypothesis = result["analysis"]["hypotheses"][0]
        self.assertEqual(len(hypothesis["supporting_fact_ids"]), 2)
        obs = {item["fact_id"]: item for item in result["analysis"]["observations"]}
        for fid in hypothesis["supporting_fact_ids"]:
            self.assertEqual(obs[fid]["source_evidence_context"]["case_id"], case["case_id"])
            self.assertEqual(obs[fid]["source_evidence_context"]["observed_at"], "2026-10-09")
        self.assertEqual(result["seller_intent"], "UNKNOWN")

    def test_unverified_or_noncurrent_facts_are_preserved_but_not_qualified(self):
        for flags in ({"verified": False}, {"current": False}, {"usable": False}):
            with self.subTest(flags=flags):
                case = self.load()
                self.store.add_evidence(case["case_id"], fact(**flags), "trusted", "source-" + str(flags))
                result = self.store.add_evidence(case["case_id"], fact("current_use", "VACANT"), "trusted", "vacant-" + str(flags))
                self.assertEqual(result["lane"], "PROPERTY_RESEARCH")
                self.assertTrue(result["evidence"])

    def test_wrong_identity_and_unsafe_sources_and_control_fields_rejected(self):
        case = self.load()
        for data in (fact(parcel_id="OTHER"), fact(source_url="javascript:alert(1)"), fact(source_url="https://u:pw@example.test"), fact(field="seller_score"), fact(value={"project_status": "COMPLETED"}), fact(observed_at="2099-10-10"), fact(verified="true")):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    self.store.add_evidence(case["case_id"], data, "trusted", "bad-event")
        self.assertEqual(len(self.store.case(case["case_id"])["evidence"]), 0)

    def test_source_correction_preserves_old_record_and_disables_old_fact(self):
        case = self.load()
        self.store.add_evidence(case["case_id"], fact(), "trusted", "source-1")
        self.store.add_evidence(case["case_id"], fact("current_use", "VACANT"), "trusted", "source-2")
        result = self.store.add_evidence(case["case_id"], fact("current_use", "OCCUPIED", supersedes="source-2"), "trusted", "correction-1")
        old = [obs for obs in result["analysis"]["observations"] if obs["field"] == "current_use" and obs["value"] == "VACANT"][0]
        self.assertFalse(old["usable_for_pattern"])
        self.assertEqual(old["source_evidence_context"]["quality_state"], "SUPERSEDED")
        self.assertEqual(len(result["evidence"]), 3)
        self.assertTrue([event for event in result["evidence"] if event["event_id"] == "source-2"][0]["superseded"])
        self.assertEqual(result["lane"], "PROPERTY_RESEARCH")
        self.assertFalse(any(hyp["operator_review_eligible"] for hyp in result["analysis"]["hypotheses"]))
        self.assertTrue(any(obs["field"] == "current_use" and obs["value"] == "OCCUPIED" and obs["usable_for_pattern"] for obs in result["analysis"]["observations"]))

    def test_correction_cannot_target_other_property_or_fact(self):
        self.load(payload(2))
        one, two = self.store.list_cases()
        self.store.add_evidence(one["case_id"], fact(), "trusted", "source-1")
        for cid, data in ((two["case_id"], fact(supersedes="source-1")), (one["case_id"], fact("current_use", "VACANT", supersedes="source-1"))):
            with self.assertRaises(ValueError):
                self.store.add_evidence(cid, data, "trusted", "correction")

    def test_new_source_import_preserves_captured_evidence_state_and_pilot(self):
        case = self.load()
        self.store.add_evidence(case["case_id"], fact(), "trusted", "source-1")
        self.store.set_state(case["case_id"], "WAITING", "Pending source", "trusted", "state-1")
        newer = payload()
        newer["generated_at"] = "2026-10-10T00:00:00Z"
        self.store.import_payload(newer, "trusted")
        result = self.store.case(case["case_id"])
        self.assertEqual(result["state"], "WAITING")
        self.assertTrue(result["pilot"])
        self.assertEqual(len(result["evidence"]), 1)
        self.assertTrue(any(obs["field"] == "project_status" for obs in result["analysis"]["observations"]))

    def test_explicitly_emptied_pilot_is_not_repopulated_on_refresh(self):
        case = self.load()
        self.store.set_pilot(case["case_id"], False, "trusted", "pilot-remove")
        newer = payload()
        newer["generated_at"] = "2026-10-10T00:00:00Z"
        self.store.import_payload(newer, "trusted")
        self.assertFalse(self.store.case(case["case_id"])["pilot"])

    def test_case_missing_from_later_export_is_preserved(self):
        self.load(payload(2))
        self.store.import_payload(payload(), "trusted")
        self.assertEqual(len(self.store.list_cases()), 2)
        self.assertEqual(len(self.store.export_payload()["imports"]), 2)

    def test_public_self_sale_needs_explicit_property_reference(self):
        case = self.load()
        result = self.store.add_evidence(case["case_id"], public(property_specific=False), "trusted", "public-1")
        self.assertEqual(result["seller_intent"], "UNKNOWN")
        result = self.store.add_evidence(case["case_id"], public(supersedes="public-1"), "trusted", "public-2")
        self.assertEqual(result["seller_intent"], "EXPRESSED_SALE_PLAN_SOURCE_ATTESTED")
        self.assertEqual(result["lane"], "SELLER_REVIEW")
        self.assertEqual(len(result["evidence"]), 2)

    def test_public_capture_requires_verified_identity_and_valid_attribution(self):
        case = self.load()
        for data in (public(identity_verified=False), public(identity_method="NAME_MATCH"), public(statement_kind="INVENTED_KIND"), public(access="PRIVATE_UNAUTHORIZED")):
            with self.assertRaises(ValueError):
                self.store.add_evidence(case["case_id"], data, "trusted", "bad-public")
        self.assertEqual(len(self.store.case(case["case_id"])["evidence"]), 0)

    def test_public_evidence_marked_unusable_is_retained_as_context(self):
        case = self.load()
        result = self.store.add_evidence(case["case_id"], public(usable=False), "trusted", "public-1")
        self.assertEqual(result["seller_intent"], "UNKNOWN")
        self.assertEqual(result["lane"], "PROPERTY_RESEARCH")
        self.assertIn("OPERATOR_MARKED_UNUSABLE", result["analysis"]["public_context"]["statements"][0]["context_reasons"])

    def test_root_form_optional_empty_identity_url_normalizes(self):
        case = self.load()
        data = public(identity_source_url="", source_url="")
        result = self.store.add_evidence(case["case_id"], data, "trusted", "public-1")
        self.assertEqual(result["lane"], "SELLER_REVIEW")

    def test_review_references_exact_stored_hypothesis_and_server_actor(self):
        case = self.load(payload(seller=True))
        hyp = case["analysis"] if "analysis" in case else self.store.case(case["case_id"])["analysis"]
        data = {"analysis_id": case["analysis_id"], "hypothesis_id": hyp["hypotheses"][0]["hypothesis_id"], "outcome": "FALSE_POSITIVE", "method": "OPERATOR_REVIEW", "detail": "Synthetic disproving inspection.", "verified": True, "actor": "client-forged"}
        result = self.store.review(case["case_id"], data, "trusted-server-actor", "review-1")
        self.assertEqual(result["analysis"]["hypotheses"][0]["challenge"]["support"], "DISPROVED_BY_REVIEW")
        event = [event for event in result["history"] if event["kind"] == "REVIEW"][0]
        self.assertEqual(event["data"]["actor"], "trusted-server-actor")
        with self.assertRaises(ValueError):
            self.store.review(case["case_id"], {**data, "hypothesis_id": "unknown"}, "trusted", "review-bad")

    def test_review_cannot_reference_another_case_or_confirm_without_owner(self):
        self.load(payload(2, seller=True))
        one, two = self.store.list_cases()
        hyp = self.store.case(one["case_id"])["analysis"]["hypotheses"][0]
        data = {"analysis_id": one["analysis_id"], "hypothesis_id": hyp["hypothesis_id"], "outcome": "SELLER_REASON_CONFIRMED", "method": "AUTHORITATIVE_RECORD", "detail": "Synthetic finding.", "verified": True}
        with self.assertRaises(ValueError):
            self.store.review(two["case_id"], data, "trusted", "review-1")
        with self.assertRaises(ValueError):
            self.store.review(one["case_id"], data, "trusted", "review-1")
        result = self.store.review(one["case_id"], {**data, "method": "OWNER_DISCLOSURE"}, "trusted", "review-1")
        self.assertTrue(any(event["kind"] == "REVIEW" for event in result["history"]))

    def negative_review(self, case, event_id):
        hyp = case["analysis"]["hypotheses"][0]
        self.store.review(case["case_id"], {"analysis_id": case["analysis_id"], "hypothesis_id": hyp["hypothesis_id"], "outcome": "FALSE_POSITIVE", "method": "OPERATOR_REVIEW", "detail": "Synthetic finding excludes this unchanged explanation.", "verified": True}, "trusted", event_id)
        return hyp["hypothesis_id"]

    def test_duplicate_typed_source_recapture_does_not_bypass_verified_negative(self):
        case = self.load()
        self.store.add_evidence(case["case_id"], fact(), "trusted", "source-1")
        current = self.store.add_evidence(case["case_id"], fact("current_use", "VACANT"), "trusted", "source-2")
        hypothesis_id = self.negative_review(current, "review-1")
        self.store.add_evidence(case["case_id"], fact(), "different-operator", "source-duplicate-1")
        result = self.store.add_evidence(case["case_id"], fact("current_use", "VACANT"), "different-operator", "source-duplicate-2")
        hyp = result["analysis"]["hypotheses"][0]
        self.assertEqual(hyp["hypothesis_id"], hypothesis_id)
        self.assertFalse(hyp["operator_review_eligible"])
        self.assertEqual(hyp["challenge"]["support"], "DISPROVED_BY_REVIEW")
        self.assertEqual(len(result["evidence"]), 4)

    def test_duplicate_public_source_recapture_does_not_bypass_verified_negative(self):
        case = self.load()
        current = self.store.add_evidence(case["case_id"], public(), "trusted", "public-1")
        hypothesis_id = self.negative_review(current, "review-1")
        result = self.store.add_evidence(case["case_id"], public(), "different-operator", "public-duplicate")
        self.assertEqual(len(result["analysis"]["hypotheses"]), 1)
        for hyp in result["analysis"]["hypotheses"]:
            self.assertEqual(hyp["hypothesis_id"], hypothesis_id)
            self.assertFalse(hyp["operator_review_eligible"])
            self.assertEqual(hyp["challenge"]["support"], "DISPROVED_BY_REVIEW")
        self.assertEqual(result["seller_intent"], "UNKNOWN")

    def test_local_reopen_restores_full_case_and_memory(self):
        case = self.load()
        self.store.add_evidence(case["case_id"], fact(), "trusted", "source-1")
        reopened = ReviewStore(self.path)
        self.assertTrue(reopened.ready())
        self.assertEqual(reopened.case(case["case_id"]), self.store.case(case["case_id"]))
        backup = reopened.export_payload()
        self.assertEqual(len(backup["imports"]), 1)
        self.assertTrue(backup["memory"])
        json.dumps(backup, allow_nan=False)

    def test_pilot_is_bounded_audited_and_does_not_qualify_closed_case(self):
        self.load(payload(7))
        cases = self.store.list_cases()
        in_pilot = [case for case in cases if case["pilot"]]
        outside = [case for case in cases if not case["pilot"]]
        with self.assertRaises(ValueError):
            self.store.set_pilot(outside[0]["case_id"], True, "trusted", "pilot-add")
        self.store.set_pilot(in_pilot[0]["case_id"], False, "trusted", "pilot-remove")
        result = self.store.set_pilot(outside[0]["case_id"], True, "trusted", "pilot-add")
        self.assertTrue(result["pilot"])
        self.assertEqual(sum(case["pilot"] for case in self.store.list_cases()), 5)
        self.store.set_pilot(outside[0]["case_id"], True, "trusted", "pilot-add")
        closed = payload(1, closed=True)
        closed["profiles"][0]["parcel_id"] = "SYNTHETIC-CLOSED"
        closed["profiles"][0]["property_address"] = "CLOSED SYNTHETIC TEST RD"
        self.store.import_payload(closed, "trusted")
        held = [case for case in self.store.list_cases() if case["parcel_id"] == "SYNTHETIC-CLOSED"][0]
        self.assertEqual(held["lane"], "HELD")
        self.assertFalse(held["pilot"])
        with self.assertRaises(ValueError):
            self.store.set_pilot(held["case_id"], True, "trusted", "pilot-closed")


if __name__ == "__main__":
    unittest.main()
