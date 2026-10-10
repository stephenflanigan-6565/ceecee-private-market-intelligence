"""Synthetic regression cases grounded in the native FIND profile contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opportunity_intelligence import InputError, evaluate_payload


def route(name="LAND_PROPERTY_UTILIZATION", state="ACTIVE_CORROBORATED_RESEARCH_ROUTE"):
    return {"route": name, "state": state,
            "noticed_because": "Land/improvement relationship survives existing internal causal triage",
            "supporting_evidence": ["NONZERO_IMPROVEMENT_ASSESSMENT_CONFIRMS_AN_IMPROVEMENT_IS_RECOGNIZED",
                                    "RECORDED_LIVING_AREA_CORROBORATES_SMALL_IMPROVEMENT_RELATIVE_TO_CLASS"],
            "actual_values": {"land_assessment": 900000, "improvement_assessment": 100000, "living_sqft": 900},
            "next_question": "Which site constraint would change this opportunity hypothesis?",
            "does_not_equal_seller_intent": True}


def profile(routes=None, address="10 SYNTHETIC EXAMPLE RD", pid="SYNTHETIC-PARCEL"):
    return {"parcel_id": pid, "property_address": address,
            "owner_identity": {"names": [], "verification_state": "UNKNOWN"},
            "why_pmi_noticed_it": routes if routes is not None else [route()],
            "current_find_state": "NO_ACTIVE_ROUTE_FROM_CURRENT_INTEGRATED_RAILS",
            "contradictions_and_unknowns": ["OWNER_CONTROL_UNKNOWN", "GEOMETRY_SOURCE_TIMEOUT_NONBLOCKING"],
            "seller_intent": "UNKNOWN", "contact_authorized": False}


def envelope(profiles=None):
    rows = profiles if profiles is not None else [profile()]
    return {"status": "ok", "version": "FIND13", "generated_at": "2026-10-04T00:00:00Z",
            "source": {"label": "EXPLICITLY_SYNTHETIC_FIXTURE", "synthetic": True},
            "profiles": rows, "profile_payload": {"total": len(rows), "returned": len(rows), "complete": True}}


def form_result(code="210", state="VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM"):
    return {"parcel_id": "SYNTHETIC-PARCEL", "property_address": "10 SYNTHETIC EXAMPLE RD",
            "observed_prop_type": code, "source_evidence_state": "AUTHORITATIVE_PROPERTY_TYPE_FACT_PRESENT",
            "state": state, "hypothesis": "OU_004_PROPERTY_FORM", "seller_intent": "UNKNOWN"}


def site_result():
    return {"parcel_id": "SYNTHETIC-PARCEL", "property_address": "10 SYNTHETIC EXAMPLE RD",
            "state": "RESIDENTIAL_INFILL_SITE_HYPOTHESIS_SUPPORTED_BUT_CONSTRAINT_UNRESOLVED",
            "opportunity_branch": "OU_005_INFILL_RESIDENTIAL_SITE",
            "hypothesis": "Supported property form plus residential zoning context",
            "property_form_evidence": {"observed_prop_type": "312", "state": "SUPPORTED_PROPERTY_FORM_HYPOTHESIS"},
            "existing_site_use_context": {"zone_code": "R1"},
            "corroboration": ["VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM", "SINGLE_RESIDENTIAL_ZONE_CONTEXT_RESOLVED"],
            "contradictions_and_unknowns": ["ACCESS_NOT_PROVEN", "SITE_CONSTRAINTS_NOT_PROVEN"],
            "next_best_question": "Which site constraint would change this infill hypothesis?",
            "why_pmi_noticed_it": ["PRIOR_LAND_DOMINANT_UNDER_IMPROVEMENT_RELATIONSHIP"]}


class OpportunityIntelligenceTests(unittest.TestCase):
    def one(self, payload):
        result = evaluate_payload(payload)
        self.assertEqual(result["summary"]["properties_evaluated"], 1)
        return result, result["cases"][0]

    def test_supported_address_without_owner_advances_with_unknowns(self):
        result, case = self.one(envelope())
        self.assertTrue(case["operator_review_eligible"])
        self.assertEqual(case["owner_identity"]["names"], [])
        self.assertEqual(case["disposition"], "SUPPORTED_PROPERTY_INVESTIGATION")
        self.assertEqual(case["reported_contradictions_and_unknowns"], profile()["contradictions_and_unknowns"])
        self.assertEqual(result["summary"]["operator_review_candidates"], 1)

    def test_support_does_not_infer_seller_motivation_or_contact(self):
        source = envelope()
        source["profiles"][0].update(seller_intent="MOTIVATED", contact_authorized=True)
        _, case = self.one(source)
        self.assertEqual(case["seller_intent"], "UNKNOWN")
        self.assertFalse(case["contact_authorized"])
        self.assertEqual(case["source_records"][0]["record"]["seller_intent"], "MOTIVATED")

    def test_unexplained_age_and_halo_do_not_qualify_by_route_count(self):
        source = envelope([profile([route("AGE_MISMATCH", "ACTIVE_RESEARCH_ROUTE"),
                                    route("REDEVELOPMENT_HALO", "ACTIVE_RESEARCH_ROUTE")])])
        _, case = self.one(source)
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["disposition"], "RESEARCH_HYPOTHESIS")

    def test_duplicate_route_does_not_multiply_support_or_revision(self):
        source = envelope()
        _, before = self.one(source)
        source["profiles"][0]["why_pmi_noticed_it"].append(copy.deepcopy(route()))
        _, after = self.one(source)
        self.assertEqual(len(after["hypotheses"]), 1)
        self.assertEqual(after["hypotheses"][0]["supporting_observations"], before["hypotheses"][0]["supporting_observations"])
        self.assertEqual(before["case_revision"], after["case_revision"])

    def test_closed_explanation_does_not_kill_supported_alternative(self):
        closed = route("ASSESSMENT_PROPERTY_RELATIONSHIP", "EXPLAINED_ROUTE_CLOSED")
        _, case = self.one(envelope([profile([closed, route()])]))
        self.assertTrue(case["operator_review_eligible"])
        self.assertEqual({hypothesis["disposition"] for hypothesis in case["hypotheses"]}, {"CLOSED", "SUPPORTED"})

    def test_same_explanation_with_conflicting_source_decisions_is_held(self):
        closed = route(state="EXPLAINED_ROUTE_CLOSED")
        _, case = self.one(envelope([profile([route(), closed])]))
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["disposition"], "CONFLICT_REQUIRES_RECONCILIATION")

    def test_targeted_conflict_retained_without_automatic_operator_task(self):
        targeted = route(state="TARGETED_FACT_REQUIRED")
        targeted["contradictions_or_quality_flags"] = ["ZERO_IMPROVEMENT_ASSESSMENT_CONTRADICTED_BY_SUBSTANTIAL_RECORDED_LIVING_SQFT"]
        _, case = self.one(envelope([profile([targeted])]))
        self.assertEqual(case["disposition"], "RESEARCH_HYPOTHESIS")
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["hypotheses"][0]["variants"][0]["record"]["contradictions_or_quality_flags"], targeted["contradictions_or_quality_flags"])

    def test_closed_plus_owner_context_does_not_reopen_property(self):
        routes = [route(state="EXPLAINED_ROUTE_CLOSED"), {"route": "OWNERSHIP_CONTEXT", "state": "CONTEXT_ONLY_NOT_QUALIFYING"}]
        _, case = self.one(envelope([profile(routes)]))
        self.assertEqual(case["disposition"], "CLOSED_EXPLANATIONS_ONLY")

    def test_empty_support_or_price_alone_does_not_qualify(self):
        unsupported = route()
        unsupported["supporting_evidence"] = [None, "", {}]
        source = envelope([profile([unsupported])])
        source["profiles"][0].update(estimated_price=25000000, apparent_equity=20000000)
        _, case = self.one(source)
        self.assertFalse(case["operator_review_eligible"])

    def test_missing_address_preserves_reasoning_but_cannot_anchor_handoff(self):
        _, case = self.one(envelope([profile(address=None)]))
        self.assertEqual(case["disposition"], "ADDRESS_REQUIRED")
        self.assertEqual(case["hypotheses"][0]["disposition"], "SUPPORTED")
        self.assertFalse(case["operator_review_eligible"])

    def test_same_parcel_conflicting_addresses_does_not_choose_one_for_queue(self):
        _, case = self.one(envelope([profile(), profile(address="99 DIFFERENT SYNTHETIC RD")]))
        self.assertEqual(case["disposition"], "ADDRESS_CONFLICT")
        self.assertFalse(case["operator_review_eligible"])

    def test_stale_top_level_state_is_not_eligibility_authority(self):
        _, case = self.one(envelope())
        self.assertTrue(case["operator_review_eligible"])
        self.assertIn("Which site constraint", case["next_check"])

    def test_partial_export_does_not_claim_market_coverage(self):
        source = envelope()
        source["profile_payload"] = {"total": 244, "returned": 1, "complete": False}
        result, _ = self.one(source)
        self.assertFalse(result["coverage"]["source_exports"][0]["complete_export_established"])
        self.assertFalse(result["coverage"]["full_market_coverage_established"])

    def test_false_complete_claim_is_not_trusted(self):
        source = envelope()
        source["profile_payload"]["total"] = 244
        result, _ = self.one(source)
        self.assertFalse(result["coverage"]["source_exports"][0]["complete_export_established"])

    def test_unknown_categories_preserved_without_new_registry(self):
        source = envelope()
        source["profiles"][0]["categories"] = ["EXISTING_USER_CATEGORY", "OU-999"]
        result, case = self.one(source)
        self.assertIn("OU-999", case["categories"])
        self.assertTrue(case["operator_review_eligible"])
        self.assertFalse(result["coverage"]["canonical_226_concept_taxonomy_loaded"])

    def test_unknown_state_not_promoted(self):
        _, case = self.one(envelope([profile([route(state="FUTURE_UNREGISTERED_STATE")])]))
        self.assertEqual(case["disposition"], "UNCLASSIFIED")

    def test_form_contradiction_closes_only_vacancy_not_land(self):
        result, case = self.one({"snapshots": [envelope(), {"version": "FIND17", "results": [form_result()]}]})
        self.assertTrue(case["operator_review_eligible"])
        self.assertEqual(next(item for item in case["hypotheses"] if item["route"] == "OU_004_PROPERTY_FORM")["disposition"], "CLOSED")

    def test_supported_form_can_advance_with_unresolved_site_constraints(self):
        _, case = self.one({"version": "FIND17", "results": [form_result("312", "SUPPORTED_PROPERTY_FORM_HYPOTHESIS")]})
        self.assertTrue(case["operator_review_eligible"])

    def test_infill_combination_survives_nonblocking_unknowns(self):
        _, case = self.one({"version": "FIND18", "results": [site_result()]})
        self.assertTrue(case["operator_review_eligible"])
        self.assertIn("OU_005_INFILL_RESIDENTIAL_SITE", case["categories"])

    def test_conflicting_form_facts_hold_infill_but_keep_independent_land(self):
        sources = [envelope(), {"version": "FIND17", "results": [form_result()]},
                   {"version": "FIND18", "results": [site_result()]}]
        _, case = self.one({"snapshots": sources})
        self.assertTrue(case["operator_review_eligible"])
        infill = next(item for item in case["hypotheses"] if item["route"] == "OU_005_INFILL_RESIDENTIAL_SITE")
        self.assertEqual(infill["disposition"], "CONFLICT")
        self.assertIn("CONFLICTING_PROPERTY_FORM_OBSERVATIONS", infill["conflicts"])

    def test_internally_contradictory_supported_form_is_not_promoted(self):
        _, case = self.one({"version": "FIND17", "results": [form_result("210", "SUPPORTED_PROPERTY_FORM_HYPOTHESIS")]})
        self.assertFalse(case["operator_review_eligible"])

    def test_native_source_policy_is_preserved_without_overriding_decisions(self):
        source = envelope([profile([route(state="ACTIVE_RESEARCH_ROUTE")])])
        source["version"] = "FIND4"
        source["policy"] = {"seller_intent": "MOTIVATED", "operator_review_eligible": True}
        _, case = self.one(source)
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["seller_intent"], "UNKNOWN")
        self.assertEqual(case["source_records"][0]["source_metadata"]["policy"], source["policy"])

    def test_unsupported_property_form_code_remains_research(self):
        _, case = self.one({"version": "FIND17", "results": [form_result("999", "SUPPORTED_PROPERTY_FORM_HYPOTHESIS")]})
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["disposition"], "RESEARCH_HYPOTHESIS")

    def test_native_padded_property_form_code_is_supported(self):
        _, case = self.one({"version": "FIND17", "results": [form_result(" 312suffix ", "SUPPORTED_PROPERTY_FORM_HYPOTHESIS")]})
        self.assertTrue(case["operator_review_eligible"])

    def test_infill_requires_supported_form_and_residential_zone(self):
        variants = []
        for code in ("210", "999", None):
            candidate = site_result()
            candidate["property_form_evidence"]["observed_prop_type"] = code
            variants.append(candidate)
        for zone in ("B1", None):
            candidate = site_result()
            candidate["existing_site_use_context"]["zone_code"] = zone
            variants.append(candidate)
        candidate = site_result()
        candidate.pop("property_form_evidence")
        variants.append(candidate)
        for candidate in variants:
            with self.subTest(candidate=candidate):
                _, case = self.one({"version": "FIND18", "results": [candidate]})
                self.assertFalse(case["operator_review_eligible"])

    def test_specialized_site_use_requires_its_own_zone_context(self):
        candidate = site_result()
        candidate["state"] = "SPECIALIZED_SITE_USE_HBU_HYPOTHESIS_SUPPORTED"
        candidate["opportunity_branch"] = "OU_012_HIGHER_BETTER_USE_SPECIALIZED_SITE_USE"
        for zone, expected in (("B1", True), ("HC", True), ("PC", True), ("R1", False)):
            candidate["existing_site_use_context"]["zone_code"] = zone
            with self.subTest(zone=zone):
                _, case = self.one({"version": "FIND18", "results": [candidate]})
                self.assertEqual(case["operator_review_eligible"], expected)

    def test_targeted_material_conflict_holds_same_hypothesis_only(self):
        targeted = route(state="TARGETED_FACT_REQUIRED")
        _, case = self.one(envelope([profile([route(), targeted])]))
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["hypotheses"][0]["disposition"], "CONFLICT")
        alternative = route("SYNTHETIC_INDEPENDENT_ALTERNATIVE")
        _, case = self.one(envelope([profile([route(), targeted, alternative])]))
        self.assertTrue(case["operator_review_eligible"])
        self.assertEqual(next(h for h in case["hypotheses"] if h["route"] == targeted["route"])["disposition"], "CONFLICT")

    def test_different_supported_vacancy_codes_preserve_site_opportunity(self):
        sources = [{"version": "FIND17", "results": [form_result("311", "SUPPORTED_PROPERTY_FORM_HYPOTHESIS")]},
                   {"version": "FIND18", "results": [site_result()]}]
        _, case = self.one({"snapshots": sources})
        infill = next(h for h in case["hypotheses"] if h["route"] == "OU_005_INFILL_RESIDENTIAL_SITE")
        self.assertEqual(infill["disposition"], "SUPPORTED")
        self.assertTrue(case["operator_review_eligible"])
        self.assertTrue(infill["fact_disagreements"])
        self.assertFalse(infill["conflicts"])

    def test_unique_same_market_address_enrichment_merges_without_duplicate_review(self):
        address_only = profile(pid=None)
        prior = evaluate_payload(envelope([address_only]))["cases"][0]
        result, enriched = self.one(envelope([address_only, profile()]))
        self.assertEqual(result["summary"]["operator_review_candidates"], 1)
        self.assertEqual(enriched["parcel_id"], "SYNTHETIC-PARCEL")
        self.assertIn(prior["case_id"], [alias["case_id"] for alias in enriched["identity_aliases"]])
        self.assertEqual(len(enriched["source_records"]), 2)

    def test_ambiguous_address_mapping_is_held_without_merging_distinct_parcels(self):
        result = evaluate_payload(envelope([profile(pid=None), profile(pid="PARCEL-A"), profile(pid="PARCEL-B")]))
        self.assertEqual(result["summary"]["properties_evaluated"], 3)
        ambiguous = next(case for case in result["cases"] if case["parcel_id"] is None)
        self.assertEqual(ambiguous["disposition"], "IDENTITY_CONFLICT")
        self.assertFalse(ambiguous["operator_review_eligible"])

    def test_address_matching_does_not_merge_different_markets(self):
        first, second = profile(pid=None), profile()
        first["market_code"], second["market_code"] = "MARKET-A", "MARKET-B"
        result = evaluate_payload(envelope([first, second]))
        self.assertEqual(result["summary"]["properties_evaluated"], 2)

    def test_deep_json_has_an_input_error_instead_of_a_server_failure(self):
        value = "leaf"
        for _ in range(600):
            value = {"nested": value}
        source = envelope()
        source["profiles"][0]["context"] = value
        with self.assertRaises(InputError):
            evaluate_payload(source)

    def test_malformed_owner_names_are_rejected_as_input(self):
        source = envelope()
        source["profiles"][0]["owner_identity"]["names"] = [{"name": "SYNTHETIC"}]
        with self.assertRaises(InputError):
            evaluate_payload(source)

    def test_owner_context_cannot_supply_opportunity_support_even_if_mislabeled(self):
        _, case = self.one(envelope([profile([route("OWNERSHIP_CONTEXT")])]))
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["disposition"], "CONTEXT_ONLY")

    def test_find17_requires_authoritative_form_evidence_even_with_generic_labels(self):
        candidate = form_result("312", "SUPPORTED_PROPERTY_FORM_HYPOTHESIS")
        candidate["source_evidence_state"] = "UNKNOWN_NONBLOCKING_SOURCE_FAILURE"
        candidate["supporting_evidence"] = ["UNVERIFIED_FORM_LABEL"]
        _, case = self.one({"version": "FIND17", "results": [candidate]})
        self.assertFalse(case["operator_review_eligible"])
        self.assertEqual(case["disposition"], "RESEARCH_HYPOTHESIS")

    def test_failed_form_source_cannot_contradict_verified_site_use_premise(self):
        candidate = form_result()
        candidate["source_evidence_state"] = "UNKNOWN_NONBLOCKING_SOURCE_FAILURE"
        _, case = self.one({"snapshots": [{"version": "FIND17", "results": [candidate]},
                                         {"version": "FIND18", "results": [site_result()]}]})
        infill = next(h for h in case["hypotheses"] if h["route"] == "OU_005_INFILL_RESIDENTIAL_SITE")
        self.assertEqual(infill["disposition"], "SUPPORTED")

    def test_known_native_versions_cannot_borrow_other_source_schema_or_states(self):
        for version in ("FIND17", "FIND18"):
            source = envelope()
            source["version"] = version
            with self.subTest(version=version), self.assertRaises(InputError):
                evaluate_payload(source)
        candidate = site_result()
        candidate["state"] = "SUPPORTED_PROPERTY_FORM_HYPOTHESIS"
        _, case = self.one({"version": "FIND18", "results": [candidate]})
        self.assertEqual(case["disposition"], "UNCLASSIFIED")
        self.assertFalse(case["operator_review_eligible"])

    def test_case_revision_tracks_evidence_not_export_clock(self):
        source = envelope()
        _, first = self.one(source)
        source["generated_at"] = "2026-10-09T00:00:00Z"
        _, second = self.one(source)
        self.assertEqual(first["case_revision"], second["case_revision"])
        source["profiles"][0]["why_pmi_noticed_it"][0]["actual_values"]["living_sqft"] = 1000
        _, third = self.one(source)
        self.assertEqual(first["case_id"], third["case_id"])
        self.assertNotEqual(first["case_revision"], third["case_revision"])

    def test_case_revision_tracks_provenance(self):
        source = envelope()
        _, first = self.one(source)
        source["source"]["label"] = "DIFFERENT_SYNTHETIC_SOURCE"
        _, second = self.one(source)
        self.assertNotEqual(first["case_revision"], second["case_revision"])

    def test_input_unchanged_and_evaluation_has_no_network_or_database(self):
        source = envelope()
        before = copy.deepcopy(source)
        with patch("socket.create_connection", side_effect=AssertionError("network called")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("HTTP called")):
            first = evaluate_payload(source)
            second = evaluate_payload(source)
        self.assertEqual(source, before)
        self.assertEqual(first, second)
        self.assertEqual(first["database_writes"], 0)
        self.assertFalse(first["guards"]["external_calls"])

    def test_malformed_sources_and_fetch_controls_rejected(self):
        invalid = [[], {}, {"profiles": "bad"}, {"profiles": [{}]}, {"version": "FIND20", "cases": []},
                   {"profiles": [], "refresh": True}, {"profiles": [], "DATABASE_URL": "ignored"},
                   {"status": "error", "profiles": []}, {"profiles": [], "version": {}},
                   {"version": "FIND18", "results": [{"parcel_id": "p", "state": []}]},
                   envelope([profile(["FIND18 string-reason shape is not a profile route"])]),
                   {"snapshots": [{"profiles": [], "path": "not a data source"}]}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(InputError):
                evaluate_payload(value)

    def test_nonfinite_json_rejected(self):
        source = envelope()
        source["profiles"][0]["value"] = float("nan")
        with self.assertRaises(InputError):
            evaluate_payload(source)

    def test_empty_valid_export_is_empty(self):
        result = evaluate_payload(envelope([]))
        self.assertEqual(result["cases"], [])
        self.assertEqual(result["review_queue"], [])

    def test_cli_keeps_input_and_writes_explicit_output(self):
        script = Path(__file__).resolve().parents[1] / "opportunity_intelligence.py"
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.json"
            output = Path(folder) / "output.json"
            original = json.dumps(envelope())
            source.write_text(original)
            run = subprocess.run([sys.executable, str(script), "--input", str(source), "--output", str(output)], capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(source.read_text(), original)
            self.assertEqual(json.loads(output.read_text())["summary"]["operator_review_candidates"], 1)
            blocked = subprocess.run([sys.executable, str(script), "--input", str(source), "--output", str(source)], capture_output=True)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(source.read_text(), original)


if __name__ == "__main__":
    unittest.main()
