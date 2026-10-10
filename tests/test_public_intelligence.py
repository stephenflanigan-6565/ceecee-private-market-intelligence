import copy
import unittest
from unittest.mock import patch

from public_intelligence import build_public_context


def cases():
    return [{"case_id": "case-one", "parcel_id": "parcel-one",
             "property_address": "1 Synthetic Test Road", "market_code": "market-one"}]


def public_information(kind="EXPLICIT_SELLING_PLAN"):
    return {
        "people": [{"person_id": "person-one", "display_name": "Synthetic Owner"}],
        "property_links": [{"person_id": "person-one", "parcel_id": "parcel-one",
                            "relationship": "OWNER", "method": "AUTHORITATIVE_RECORD",
                            "verified": True, "verified_by": "operator",
                            "source_record_id": "synthetic-record"}],
        "statements": [{"statement_id": "statement-one", "person_id": "person-one",
                        "quote": "I am considering selling this property.", "kind": kind,
                        "about": "SELF", "access": "PUBLIC", "captured_at": "2026-10-09",
                        "current": True, "verified": True, "verified_by": "operator",
                        "source_url": "https://example.invalid/synthetic-post",
                        "parcel_id": "parcel-one", "context_tags": []}],
    }


class PublicInformationTests(unittest.TestCase):
    def build(self, information=None, supplied_cases=None):
        return build_public_context(information if information is not None else public_information(),
                                    supplied_cases if supplied_cases is not None else cases(),
                                    as_of="2026-10-10")

    def statement(self, result):
        return result["by_case"]["case-one"]["statements"][0]

    def test_verified_explicit_property_statement_has_auditable_observation(self):
        result = self.build()
        statement = self.statement(result)
        observation = result["by_case"]["case-one"]["observations"][0]
        self.assertTrue(statement["usable"])
        self.assertTrue(statement["property_specific"])
        self.assertEqual(observation["fact_id"], statement["fact_id"])
        self.assertTrue(statement["fact_id"].startswith("public_"))
        self.assertEqual(observation["field"], "public_statement")
        self.assertEqual(observation["value"], statement["quote"])
        self.assertEqual(observation["metadata"]["source_provenance"]["source_url"],
                         "https://example.invalid/synthetic-post")
        self.assertFalse(statement["contact_authorized"])
        self.assertEqual(statement["seller_intent"], "UNKNOWN")

    def test_property_owner_direction_keeps_reported_owner_context_internal(self):
        result = self.build()
        self.assertEqual(result["person_findings"][0]["person"]["display_name"], "Synthetic Owner")
        self.assertEqual(result["person_findings"][0]["strong_link_case_ids"], ["case-one"])
        self.assertTrue(result["coverage"]["verification_is_operator_attestation"])

    def test_buyer_first_direction_preserves_no_owner_finding_without_inventing_sale(self):
        info = public_information("EXPLICIT_BUYING_PLAN")
        info["property_links"] = []
        info["statements"][0].pop("parcel_id")
        result = self.build(info)
        finding = result["person_findings"][0]
        self.assertTrue(finding["buyer_context_relevant"])
        self.assertTrue(finding["statement_usable"])
        self.assertFalse(finding["usable"])
        self.assertEqual(finding["matched_case_ids"], [])
        self.assertEqual(result["by_case"]["case-one"]["statements"], [])
        self.assertEqual(finding["seller_intent"], "UNKNOWN")

    def test_buyer_with_property_is_context_not_a_declared_selling_plan(self):
        result = self.build(public_information("EXPLICIT_BUYING_PLAN"))
        statement = self.statement(result)
        self.assertTrue(statement["usable"])
        self.assertEqual(statement["kind"], "EXPLICIT_BUYING_PLAN")
        self.assertEqual(statement["seller_intent"], "UNKNOWN")

    def test_name_only_link_does_not_borrow_social_motive(self):
        info = public_information()
        info["property_links"][0]["method"] = "NAME_MATCH"
        result = self.build(info)
        self.assertFalse(self.statement(result)["usable"])
        self.assertFalse(self.statement(result)["strong_property_link"])
        self.assertEqual(result["by_case"]["case-one"]["unresolved_links"][0]["unresolved_reason"],
                         "NAME_MATCH_ONLY")

    def test_unverified_ownership_remains_context(self):
        info = public_information()
        info["property_links"][0]["verified"] = False
        result = self.build(info)
        self.assertFalse(self.statement(result)["usable"])
        self.assertEqual(result["coverage"]["unresolved_links"][0]["unresolved_reason"],
                         "UNVERIFIED_PROPERTY_LINK")

    def test_no_explicit_property_reference_is_not_specific_even_for_single_owner(self):
        info = public_information()
        info["statements"][0].pop("parcel_id")
        statement = self.statement(self.build(info))
        self.assertTrue(statement["usable"])
        self.assertFalse(statement["property_specific"])

    def test_statement_about_other_property_cannot_supply_this_propertys_motive(self):
        info = public_information()
        other = {"case_id": "case-two", "parcel_id": "parcel-two",
                 "property_address": "2 Synthetic Test Road", "market_code": "market-one"}
        info["statements"][0]["parcel_id"] = "parcel-two"
        result = self.build(info, cases() + [other])
        statement = self.statement(result)
        self.assertFalse(statement["usable"])
        self.assertFalse(statement["property_specific"])
        self.assertIn("STATEMENT_REFERENCES_ANOTHER_PROPERTY", statement["context_reasons"])

    def test_duplicate_parcel_across_markets_requires_explicit_market(self):
        info = public_information()
        second = {"case_id": "case-two", "parcel_id": "parcel-one",
                  "property_address": "2 Different Market Road", "market_code": "market-two"}
        info["property_links"][0]["property_address"] = "1 Synthetic Test Road"
        result = self.build(info, cases() + [second])
        self.assertEqual(result["person_findings"][0]["matched_case_ids"], [])
        self.assertEqual(result["by_case"]["case-one"]["statements"], [])
        self.assertEqual(result["coverage"]["unresolved_links"][0]["unresolved_reason"],
                         "AMBIGUOUS_PROPERTY_REFERENCE")
        info["property_links"][0]["market_code"] = "market-one"
        info["statements"][0]["market_code"] = "market-one"
        resolved = self.build(info, cases() + [second])
        self.assertTrue(self.statement(resolved)["usable"])
        self.assertTrue(self.statement(resolved)["property_specific"])

    def test_conflicting_parcel_and_address_is_research_not_silent_join(self):
        info = public_information()
        second = {"case_id": "case-two", "parcel_id": "parcel-two",
                  "property_address": "2 Synthetic Test Road", "market_code": "market-one"}
        info["property_links"][0]["property_address"] = second["property_address"]
        result = self.build(info, cases() + [second])
        self.assertEqual(result["coverage"]["unresolved_links"][0]["unresolved_reason"],
                         "CONFLICTING_PROPERTY_REFERENCE")
        self.assertEqual(result["person_findings"][0]["matched_case_ids"], [])

    def test_life_event_keeps_its_category_and_never_becomes_sale_intent(self):
        info = public_information("ANNOUNCED_TRANSITION")
        info["statements"][0]["quote"] = "Synthetic example: I got married."
        info["statements"][0]["context_tags"] = ["MARRIAGE", "OTHER_CUSTOM_CONTEXT"]
        result = self.build(info)
        statement = self.statement(result)
        self.assertEqual(statement["kind"], "ANNOUNCED_TRANSITION")
        self.assertEqual(statement["seller_intent"], "UNKNOWN")
        self.assertFalse(statement["contact_authorized"])
        self.assertEqual(statement["context_tags"], ["MARRIAGE", "OTHER_CUSTOM_CONTEXT"])

    def test_context_conditions_preserve_observation_and_prevent_actionability(self):
        changes = [("captured_at", None, "MISSING_CAPTURE_DATE"),
                   ("captured_at", "2026-10-11", "FUTURE_CAPTURE_DATE"),
                   ("valid_until", "2026-10-09", "EXPIRED_STATEMENT"),
                   ("current", False, "NON_CURRENT_STATEMENT"),
                   ("verified", False, "UNVERIFIED_STATEMENT"),
                   ("about", "THIRD_PARTY", "THIRD_PARTY_STATEMENT")]
        for field, value, reason in changes:
            with self.subTest(field=field, value=value):
                info = public_information()
                info["statements"][0][field] = value
                result = self.build(info)
                statement = self.statement(result)
                self.assertFalse(statement["usable"])
                self.assertIn(reason, statement["context_reasons"])
                self.assertEqual(len(result["by_case"]["case-one"]["observations"]), 1)

    def test_authorized_statement_and_operator_verified_controller_are_supported(self):
        info = public_information("EXPLICIT_HOLD_PLAN")
        info["statements"][0]["access"] = "AUTHORIZED"
        info["property_links"][0].update(method="OPERATOR_VERIFIED", relationship="CONTROLLER")
        statement = self.statement(self.build(info))
        self.assertTrue(statement["usable"])
        self.assertEqual(statement["kind"], "EXPLICIT_HOLD_PLAN")

    def test_exact_duplicate_statement_deduplicated_but_conflict_rejected(self):
        info = public_information()
        info["statements"].append(copy.deepcopy(info["statements"][0]))
        result = self.build(info)
        self.assertEqual(len(result["person_findings"]), 1)
        self.assertEqual(result["coverage"]["duplicate_statements_deduplicated"], 1)
        info["statements"][1]["quote"] = "Different quote with reused identifier."
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate statement_id"):
            self.build(info)

    def test_invalid_dates_quote_provenance_and_boolean_are_rejected(self):
        changes = [("captured_at", "2026-99-10"), ("captured_at", "yesterday"),
                   ("quote", "   "), ("quote", 123), ("verified", "true"),
                   ("verified_by", None), ("access", "PRIVATE"),
                   ("source_url", "file:///private/secret"), ("context_tags", "MARRIAGE")]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                info = public_information()
                info["statements"][0][field] = value
                with self.assertRaises(ValueError):
                    self.build(info)
        info = public_information()
        info["statements"][0].pop("source_url")
        with self.assertRaisesRegex(ValueError, "source_url or source_record_id"):
            self.build(info)

    def test_unknown_person_does_not_silently_link_by_display_name(self):
        info = public_information()
        info["statements"][0]["person_id"] = "different-person"
        with self.assertRaisesRegex(ValueError, "unknown person_id"):
            self.build(info)

    def test_urls_are_inert_and_inputs_unchanged(self):
        info = public_information()
        original = copy.deepcopy(info)
        supplied_cases = cases()
        before_cases = copy.deepcopy(supplied_cases)
        with patch("urllib.request.urlopen", side_effect=AssertionError("Network access forbidden")):
            result = self.build(info, supplied_cases)
        self.assertEqual(info, original)
        self.assertEqual(supplied_cases, before_cases)
        self.assertFalse(result["coverage"]["external_calls"])
        self.assertFalse(result["coverage"]["source_access_performed"])

    def test_fact_id_stable_across_case_order_and_shared_source(self):
        info = public_information()
        second = {"case_id": "case-two", "parcel_id": "parcel-two",
                  "property_address": "2 Synthetic Test Road", "market_code": "market-one"}
        info["property_links"].append({**info["property_links"][0], "parcel_id": "parcel-two"})
        info["statements"][0].pop("parcel_id")
        result = self.build(info, cases() + [second])
        first_id = result["by_case"]["case-one"]["observations"][0]["fact_id"]
        second_id = result["by_case"]["case-two"]["observations"][0]["fact_id"]
        self.assertEqual(first_id, second_id)
        self.assertEqual(first_id, self.build(info, [second] + cases())["by_case"]["case-one"]["observations"][0]["fact_id"])

    def test_empty_public_information_retains_all_cases_without_person_guessing(self):
        result = self.build({})
        self.assertEqual(set(result["by_case"]), {"case-one"})
        self.assertEqual(result["person_findings"], [])
        self.assertFalse(result["coverage"]["social_source_coverage_established"])


if __name__ == "__main__":
    unittest.main()
