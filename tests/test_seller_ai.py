import ast
import copy
from pathlib import Path
import tempfile
import unittest

import seller_ai
from seller_ai import analyze, analyze_batch, prepare_bundle, prepare_packets
from seller_ai_memory import ReviewMemory


def snapshot(address="1 SYNTHETIC TEST RD", parcel="TEST-PARCEL"):
    return {
        "status": "ok", "version": "FIND4",
        "profile_payload": {"complete": True, "returned": 1, "total": 1},
        "profiles": [{
            "parcel_id": parcel, "property_address": address,
            "owner_identity": {"names": ["SYNTHETIC PRIVATE OWNER"]},
            "why_pmi_noticed_it": [{
                "route": "PROJECT_CONTEXT", "state": "ACTIVE_RESEARCH_ROUTE",
                "actual_values": {"project_status": "COMPLETED", "current_use": "VACANT"},
            }],
            "seller_intent": "UNKNOWN", "contact_authorized": False,
        }],
    }


def many_properties(count):
    payload = snapshot()
    template = payload["profiles"][0]
    payload["profiles"] = []
    for index in range(count):
        profile = copy.deepcopy(template)
        profile.update(parcel_id="TEST-" + str(index),
                       property_address=str(index + 1) + " SYNTHETIC TEST RD")
        payload["profiles"].append(profile)
    payload["profile_payload"] = {"complete": True, "returned": count, "total": count}
    return payload


def public_snapshot(kind="EXPLICIT_SELLING_PLAN", include_project=False):
    payload = snapshot()
    if not include_project:
        payload["profiles"][0]["why_pmi_noticed_it"] = []
    payload["public_information"] = {
        "people": [{"person_id": "person-1", "display_name": "Synthetic Owner"}],
        "property_links": [{"person_id": "person-1", "parcel_id": "TEST-PARCEL",
            "relationship": "OWNER", "method": "AUTHORITATIVE_RECORD", "verified": True,
            "verified_by": "operator", "source_record_id": "synthetic-deed"}],
        "statements": [{"statement_id": "statement-1", "person_id": "person-1",
            "quote": "A synthetic self-disclosed property plan.", "kind": kind,
            "about": "SELF", "access": "PUBLIC", "source_record_id": "synthetic-post",
            "captured_at": "2026-10-09", "verified": True, "verified_by": "operator",
            "current": True, "parcel_id": "TEST-PARCEL", "context_tags": []}],
    }
    return payload


class InternalReasoningTests(unittest.TestCase):
    def packet(self, **kwargs):
        return prepare_packets(snapshot(**kwargs))[0]

    def test_partial_source_metadata_remains_partial_without_fixed_reason_list(self):
        payload = snapshot()
        payload["profile_payload"] = {"complete": False, "returned": 1, "total": 194}
        packet = prepare_packets(payload)[0]
        self.assertFalse(packet["coverage"]["source_exports"][0]["complete_export_established"])
        self.assertEqual(packet["coverage"]["source_exports"][0]["profile_payload"]["total"], 194)
        self.assertEqual(packet["coverage"]["hypothesis_vocabulary"], "EXPANDABLE")
        self.assertFalse(packet["coverage"]["finalized_seller_reason_list_required"])

    def test_complete_export_preserves_every_case_without_claiming_full_market_coverage(self):
        bundle = prepare_bundle(many_properties(8))
        self.assertEqual(len(bundle["packets"]), 8)
        self.assertEqual(len({p["case_id"] for p in bundle["packets"]}), 8)
        for packet in bundle["packets"]:
            self.assertTrue(packet["coverage"]["source_exports"][0]["complete_export_established"])
            self.assertFalse(packet["coverage"]["full_market_coverage_established"])

    def test_unknown_owner_can_get_focused_inquiry_with_intent_unknown(self):
        payload = snapshot()
        payload["profiles"][0]["owner_identity"]["names"] = []
        result = analyze(prepare_packets(payload)[0])
        hypothesis = result["hypotheses"][0]
        self.assertTrue(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["seller_intent"], "UNKNOWN")
        self.assertEqual(result["seller_intent"], "UNKNOWN")
        self.assertFalse(hypothesis["contact_authorized"])
        self.assertEqual(result["property_address"], "1 SYNTHETIC TEST RD")

    def test_supported_hypothesis_cites_facts_and_explains_its_limits(self):
        result = analyze(self.packet())
        hypothesis = result["hypotheses"][0]
        observations = {item["fact_id"]: item for item in result["observations"]}
        self.assertEqual({observations[f]["value"] for f in hypothesis["supporting_fact_ids"]},
                         {"COMPLETED", "VACANT"})
        self.assertTrue(hypothesis["alternative_explanations"])
        self.assertTrue(hypothesis["next_check"])
        self.assertTrue(hypothesis["would_disprove"])
        self.assertEqual(hypothesis["origin"], "INTERNAL_PATTERN")

    def test_closed_project_explanation_cannot_promote_its_old_facts(self):
        payload = snapshot()
        payload["profiles"][0]["why_pmi_noticed_it"][0]["state"] = "EXPLAINED_ROUTE_CLOSED"
        packet = prepare_packets(payload)[0]
        result = analyze(packet)
        self.assertEqual(result["hypotheses"], [])
        self.assertTrue(any(item["closed_explanation"] for item in packet["observations"]))
        self.assertEqual(result["prior_route_decisions"][0]["disposition"], "CLOSED")

    def test_closed_assessment_does_not_exclude_independent_project_facts(self):
        payload = snapshot()
        payload["profiles"][0]["why_pmi_noticed_it"] = [{
            "route": "ASSESSMENT_VALUE_CONTEXT", "state": "EXPLAINED_ROUTE_CLOSED",
            "actual_values": {"assessment_timing": "Administrative cycle explains the change"},
        }]
        payload["profiles"][0]["project_context"] = {
            "project_status": "COMPLETED", "current_use": "VACANT",
        }
        result = analyze(prepare_packets(payload)[0])
        self.assertTrue(result["hypotheses"][0]["operator_review_eligible"])
        self.assertEqual(result["prior_route_decisions"][0]["disposition"], "CLOSED")
        fact_lookup = {f["fact_id"]: f for f in result["observations"]}
        self.assertTrue(all(not fact_lookup[f]["closed_explanation"]
                            for f in result["hypotheses"][0]["supporting_fact_ids"]))

    def test_explicitly_noncurrent_historical_or_invalid_project_facts_stay_context_only(self):
        contexts = (
            {"historical_project_context": {"current": False,
                "project_status": "COMPLETED", "current_use": "VACANT"}},
            {"history": {"project_context": {
                "project_status": "COMPLETED", "current_use": "VACANT"}}},
            {"project_context": {"quality_state": "INVALID",
                "project_status": "COMPLETED", "current_use": "VACANT"}},
        )
        for context in contexts:
            with self.subTest(context=context):
                payload = snapshot()
                payload["profiles"][0]["why_pmi_noticed_it"] = []
                payload["profiles"][0].update(context)
                packet = prepare_packets(payload)[0]
                result = analyze(packet)
                supplied_project_facts = [f for f in packet["observations"]
                    if f["field"] in {"project_status", "current_use"}]
                self.assertEqual(len(supplied_project_facts), 2)
                self.assertTrue(all(not f["usable_for_pattern"] for f in supplied_project_facts))
                self.assertEqual(result["hypotheses"], [])

    def test_other_propertys_nested_project_facts_cannot_qualify_the_current_case(self):
        payload = snapshot()
        payload["profiles"][0]["why_pmi_noticed_it"] = []
        payload["profiles"][0]["other_property"] = {
            "parcel_id": "DIFFERENT-SYNTHETIC-PARCEL", "project_context": {
                "project_status": "COMPLETED", "current_use": "VACANT"},
        }
        packet = prepare_packets(payload)[0]
        result = analyze(packet)
        supplied_project_facts = [f for f in packet["observations"]
            if f["field"] in {"project_status", "current_use"}]
        self.assertEqual(len(supplied_project_facts), 2)
        self.assertTrue(all(not f["usable_for_pattern"] for f in supplied_project_facts))
        self.assertEqual(result["hypotheses"], [])

    def test_nested_matching_parcel_in_a_different_market_cannot_qualify_current_case(self):
        payload = snapshot()
        payload["profiles"][0].update(market_code="MARKET-A", why_pmi_noticed_it=[])
        payload["profiles"][0]["other_property_context"] = {
            "parcel_id": "TEST-PARCEL", "market_code": "MARKET-B",
            "project_status": "COMPLETED", "current_use": "VACANT",
        }
        packet = prepare_packets(payload)[0]
        result = analyze(packet)
        self.assertEqual(packet["market_code"], "MARKET-A")
        project_facts = [f for f in packet["observations"]
                         if f["field"] in {"project_status", "current_use"}]
        self.assertEqual(len(project_facts), 2)
        self.assertTrue(all(not f["usable_for_pattern"] for f in project_facts))
        self.assertEqual(result["hypotheses"], [])

    def test_missing_address_preserves_reasoning_and_holds_handoff(self):
        result = analyze(self.packet(address=None))
        self.assertEqual(len(result["hypotheses"]), 1)
        hypothesis = result["hypotheses"][0]
        self.assertFalse(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["disposition"], "MACHINE_RESEARCH")
        self.assertIn("address", hypothesis["challenge"]["reason"])

    def test_conflicting_addresses_hold_supported_property_reasoning(self):
        payload = snapshot()
        other = copy.deepcopy(payload["profiles"][0])
        other["property_address"] = "999 DIFFERENT SYNTHETIC RD"
        payload["profiles"].append(other)
        payload["profile_payload"] = {"complete": True, "returned": 2, "total": 2}
        packet = prepare_packets(payload)[0]
        result = analyze(packet)
        self.assertTrue(packet["identity_ambiguous"])
        self.assertEqual(len(result["hypotheses"]), 1)
        self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])

    def test_conflicting_current_use_cannot_be_cherry_picked(self):
        payload = snapshot()
        payload["profiles"][0]["current_occupancy"] = {"current_use": "OCCUPIED"}
        result = analyze(prepare_packets(payload)[0])
        hypothesis = result["hypotheses"][0]
        self.assertFalse(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["challenge"]["support"], "CONTRADICTED")
        facts = {f["fact_id"]: f for f in result["observations"]}
        self.assertIn("OCCUPIED", [facts[f]["value"] for f in hypothesis["contradicting_fact_ids"]])

    def test_conflicting_project_status_cannot_be_cherry_picked(self):
        payload = snapshot()
        payload["profiles"][0]["current_permit"] = {"project_status": "IN_PROGRESS"}
        result = analyze(prepare_packets(payload)[0])
        self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])
        self.assertEqual(result["hypotheses"][0]["challenge"]["support"], "CONTRADICTED")

    def test_documented_hold_contradicts_completed_unused_exit_hypothesis(self):
        payload = snapshot()
        payload["profiles"][0]["owner_property_plan"] = {"declared_strategy": "HOLD"}
        result = analyze(prepare_packets(payload)[0])
        self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])
        self.assertTrue(result["hypotheses"][0]["contradicting_fact_ids"])

    def test_any_single_seed_condition_is_insufficient_for_this_pattern(self):
        for missing in ("project_status", "current_use"):
            with self.subTest(missing=missing):
                payload = snapshot()
                del payload["profiles"][0]["why_pmi_noticed_it"][0]["actual_values"][missing]
                result = analyze(prepare_packets(payload)[0])
                self.assertEqual(result["hypotheses"], [])

    def test_prices_equity_age_life_events_and_assessment_alone_do_not_qualify(self):
        payload = snapshot()
        payload["profiles"][0]["why_pmi_noticed_it"] = [{
            "route": "ASSESSMENT_VALUE_CONTEXT", "state": "ACTIVE_RESEARCH_ROUTE",
            "actual_values": {"assessment_jump": 900000, "estimated_equity": 20000000,
                "asking_price": 25000000, "age": 70, "marital_status": "DIVORCED",
                "children": 3, "life_event": "MARRIAGE", "location": "Luxury area"},
        }]
        result = analyze_batch(payload)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["hypotheses"], [])
        self.assertEqual(result["review_batch"], [])
        self.assertEqual(result["results"][0]["seller_intent"], "UNKNOWN")

    def test_no_price_floor_excludes_supported_property(self):
        for price in (25000, 250000, 25000000):
            with self.subTest(price=price):
                payload = snapshot()
                payload["profiles"][0]["asking_price"] = price
                self.assertTrue(analyze(prepare_packets(payload)[0])["hypotheses"][0]["operator_review_eligible"])

    def test_prepare_and_analyze_do_not_mutate_caller_data(self):
        payload = snapshot()
        original_payload = copy.deepcopy(payload)
        packet = prepare_packets(payload)[0]
        original_packet = copy.deepcopy(packet)
        analyze(packet)
        analyze_batch(payload)
        self.assertEqual(payload, original_payload)
        self.assertEqual(packet, original_packet)

    def test_stateless_results_are_repeatable_without_claiming_connected_learning(self):
        packet = self.packet()
        first, second = analyze(packet), analyze(packet)
        self.assertEqual(first, second)
        self.assertFalse(first["learning_memory_connected"])
        self.assertEqual(first["learning_method"], "STATELESS_ANALYSIS")
        self.assertEqual(first["external_calls"], 0)
        self.assertEqual(first["model_calls"], 0)

    def test_default_review_batch_is_small_and_all_cases_and_backlog_are_retained(self):
        result = analyze_batch(many_properties(8))
        self.assertEqual(len(result["results"]), 8)
        self.assertEqual(len(result["review_batch"]), 5)
        self.assertEqual(len(result["review_backlog_case_ids"]), 3)
        selected = {r["case_id"] for r in result["review_batch"]}
        backlog = set(result["review_backlog_case_ids"])
        self.assertFalse(selected & backlog)
        self.assertEqual(selected | backlog, {r["case_id"] for r in result["results"]})
        self.assertTrue(result["coverage"]["backlog_preserved"])

    def test_zero_review_limit_holds_candidates_without_erasing_results(self):
        result = analyze_batch(many_properties(3), review_limit=0)
        self.assertEqual(result["review_batch"], [])
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual(len(result["review_backlog_case_ids"]), 3)
        self.assertEqual(result["coverage"]["review_eligible_properties"], 3)

    def test_invalid_review_limits_are_rejected(self):
        for limit in (-1, 51, True, 2.5, "5"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                analyze_batch(snapshot(), review_limit=limit)

    def test_internal_engine_has_no_external_model_client_or_key_requirement(self):
        tree = ast.parse(Path(seller_ai.__file__).read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any(name.split(".")[0] in {"urllib", "requests", "httpx", "openai"}
                             for name in imported))
        self.assertFalse(hasattr(seller_ai, "OpenAIReasoner"))
        self.assertEqual(analyze_batch(snapshot())["model_calls"], 0)


class PublicPropertyIntegrationTests(unittest.TestCase):
    def result(self, payload):
        return analyze_batch(payload, as_of="2026-10-10")

    def test_attributed_current_specific_sale_plan_supports_property_inquiry(self):
        result = self.result(public_snapshot())
        hypothesis = result["results"][0]["hypotheses"][0]
        self.assertTrue(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["origin"], "PUBLIC_STATEMENT_PROPERTY_LINK")
        self.assertEqual(hypothesis["seller_intent"], "EXPRESSED_SALE_PLAN_SOURCE_ATTESTED")
        self.assertEqual(len(result["review_batch"]), 1)
        self.assertFalse(hypothesis["contact_authorized"])
        self.assertEqual(result["external_calls"], 0)

    def test_linked_buying_interest_does_not_imply_an_owned_property_must_sell(self):
        result = self.result(public_snapshot("EXPLICIT_BUYING_PLAN"))
        hypothesis = result["results"][0]["hypotheses"][0]
        self.assertFalse(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["disposition"], "MACHINE_RESEARCH")
        self.assertEqual(hypothesis["seller_intent"], "UNKNOWN")
        self.assertEqual(result["review_batch"], [])
        self.assertTrue(result["person_findings"][0]["buyer_context_relevant"])

    def test_disclosed_sell_to_buy_plan_supports_inquiry_without_inferred_requirement(self):
        result = self.result(public_snapshot("EXPLICIT_SELL_TO_BUY_PLAN"))
        self.assertTrue(result["results"][0]["hypotheses"][0]["operator_review_eligible"])
        self.assertEqual(result["results"][0]["seller_intent"], "EXPRESSED_SALE_PLAN_SOURCE_ATTESTED")

    def test_public_hold_plan_blocks_a_conflicting_public_sale_plan(self):
        payload = public_snapshot()
        hold = copy.deepcopy(payload["public_information"]["statements"][0])
        hold.update(statement_id="hold-1", kind="EXPLICIT_HOLD_PLAN",
                    quote="I plan to retain this synthetic property.", source_record_id="hold-post")
        payload["public_information"]["statements"].append(hold)
        result = self.result(payload)
        hypothesis = result["results"][0]["hypotheses"][0]
        self.assertFalse(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["challenge"]["support"], "CONTRADICTED")
        self.assertEqual(result["review_batch"], [])

    def test_current_public_hold_plan_also_blocks_project_generated_exit_inquiry(self):
        result = self.result(public_snapshot("EXPLICIT_HOLD_PLAN", include_project=True))
        hypothesis = result["results"][0]["hypotheses"][0]
        self.assertEqual(hypothesis["pattern_id"], "COMPLETED_PROJECT_UNUSED_PROPERTY")
        self.assertFalse(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["challenge"]["support"], "CONTRADICTED")
        self.assertEqual(result["review_batch"], [])

    def test_life_transition_is_retained_as_context_without_creating_sale_intent(self):
        payload = public_snapshot("ANNOUNCED_TRANSITION")
        payload["public_information"]["statements"][0].update(
            quote="A synthetic person announced a new job and marriage.",
            context_tags=["NEW_JOB", "MARRIAGE"])
        result = self.result(payload)
        self.assertEqual(len(result["person_findings"]), 1)
        self.assertEqual(result["results"][0]["hypotheses"], [])
        self.assertEqual(result["results"][0]["seller_intent"], "UNKNOWN")
        self.assertEqual(result["review_batch"], [])

    def test_name_match_or_unverified_ownership_cannot_promote_specific_sale_statement(self):
        for changes in ({"method": "NAME_MATCH"}, {"verified": False}):
            with self.subTest(changes=changes):
                payload = public_snapshot()
                payload["public_information"]["property_links"][0].update(changes)
                result = self.result(payload)
                self.assertFalse(result["results"][0]["hypotheses"][0]["operator_review_eligible"])
                self.assertEqual(result["results"][0]["seller_intent"], "UNKNOWN")

    def test_sale_plan_without_specific_property_reference_remains_machine_research(self):
        payload = public_snapshot()
        del payload["public_information"]["statements"][0]["parcel_id"]
        result = self.result(payload)
        self.assertFalse(result["results"][0]["hypotheses"][0]["operator_review_eligible"])
        self.assertEqual(result["results"][0]["seller_intent"], "UNKNOWN")

    def test_unlinked_buying_statement_is_retained_for_person_first_investigation(self):
        payload = public_snapshot("EXPLICIT_BUYING_PLAN")
        payload["public_information"]["property_links"] = []
        result = self.result(payload)
        self.assertEqual(len(result["person_findings"]), 1)
        self.assertTrue(result["person_findings"][0]["buyer_context_relevant"])
        self.assertEqual(result["person_findings"][0]["matched_case_ids"], [])
        self.assertEqual(result["results"][0]["hypotheses"], [])
        self.assertEqual(result["review_batch"], [])


class MemoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / "memory.db")
        self.memory = ReviewMemory(self.path)
        self.analysis = analyze(prepare_packets(snapshot())[0], self.memory)
        self.review = dict(event_id="event-1", analysis_id=self.analysis["analysis_id"],
            hypothesis_id=self.analysis["hypotheses"][0]["hypothesis_id"], actor="operator",
            outcome="FALSE_POSITIVE", method="OPERATOR_REVIEW",
            detail="The synthetic owner intended occupancy.", verified=True)

    def tearDown(self):
        self.directory.cleanup()

    def test_memory_survives_reopening_with_original_reasoning_and_feedback(self):
        self.memory.review(**self.review)
        reopened = ReviewMemory(self.path)
        self.assertEqual(reopened.analysis(self.analysis["analysis_id"]), self.analysis)
        self.assertEqual(len(reopened.history(self.analysis["case_id"])), 2)

    def test_replayed_analysis_and_feedback_are_idempotent(self):
        self.memory.remember_analysis(self.analysis)
        self.memory.review(**self.review)
        self.memory.review(**self.review)
        self.assertEqual(len(self.memory.history(self.analysis["case_id"])), 2)
        self.assertEqual(self.memory.lessons()[0]["reviewed_properties"], 1)

    def test_feedback_identifier_cannot_overwrite_old_finding(self):
        self.memory.review(**self.review)
        with self.assertRaisesRegex(ValueError, "overwritten"):
            self.memory.review(**{**self.review, "detail": "Different finding."})
        self.assertEqual(self.memory.lessons()[0]["outcomes"], {"FALSE_POSITIVE": 1})

    def test_verified_correction_retains_history_and_updates_lessons(self):
        self.memory.review(**self.review)
        self.memory.review(**{**self.review, "event_id": "event-2",
            "outcome": "USEFUL_INVESTIGATION", "detail": "A later review established useful inquiry.",
            "supersedes": "event-1"})
        self.assertEqual(len(self.memory.history(self.analysis["case_id"])), 3)
        self.assertEqual(self.memory.lessons()[0]["outcomes"], {"USEFUL_INVESTIGATION": 1})

    def test_unverified_feedback_is_retained_without_influencing_later_cases(self):
        self.memory.review(**{**self.review, "verified": False})
        self.assertEqual(self.memory.lessons(), [])
        other = analyze(prepare_packets(snapshot(parcel="OTHER-PARCEL"))[0], self.memory)
        self.assertEqual(other["hypotheses"][0]["comparable_reviewed_cases"], [])
        self.assertEqual(other["hypotheses"][0]["reviewed_pattern_lessons"], [])

    def test_owner_confirmation_cannot_be_recorded_as_reviewer_opinion(self):
        with self.assertRaisesRegex(ValueError, "owner"):
            self.memory.review(**{**self.review, "outcome": "SELLER_REASON_CONFIRMED"})

    def test_review_rejects_unknown_analysis_hypothesis_and_correction(self):
        for override in ({"analysis_id": "unknown"}, {"hypothesis_id": "unknown"}, {"supersedes": "unknown"}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.memory.review(**{**self.review, **override})

    def test_original_analysis_cannot_be_replaced_with_modified_reasoning(self):
        changed = copy.deepcopy(self.analysis)
        changed["hypotheses"][0]["opportunity"] = "Different reasoning."
        with self.assertRaisesRegex(ValueError, "content"):
            self.memory.remember_analysis(changed)

    def test_verified_case_is_retrieved_without_importing_its_seller_intent(self):
        self.memory.review(**{**self.review, "outcome": "SELLER_REASON_CONFIRMED",
            "method": "OWNER_DISCLOSURE", "detail": "Synthetic owner disclosed a sale plan."})
        other = analyze(prepare_packets(snapshot(parcel="OTHER-PARCEL"))[0], self.memory)
        hypothesis = other["hypotheses"][0]
        self.assertEqual(other["seller_intent"], "UNKNOWN")
        self.assertEqual(hypothesis["reviewed_pattern_lessons"][0]["outcomes"],
                         {"SELLER_REASON_CONFIRMED": 1})
        self.assertEqual(len(hypothesis["comparable_reviewed_cases"]), 1)


if __name__ == "__main__":
    unittest.main()
