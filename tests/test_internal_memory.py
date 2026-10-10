import copy
import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from seller_ai_memory import ReviewMemory, digest


def definition(pattern_id="PROJECT_EXIT_OPTIONS"):
    return {
        "pattern_id": pattern_id, "title": "Completed lease with a project exit option",
        "conditions": [{"field": "lease_status", "value": "EXPIRED"}],
        "contradictions": [{"field": "declared_strategy", "value": "HOLD"}],
        "opportunity": "Evaluate disposition options after the recorded lease term.",
        "possible_seller_reason": "A sale may fit the owner's next objective; it is unconfirmed.",
        "agent_help": "Compare hold, lease, and sale options with the owner.",
        "alternative_explanations": ["The owner may renew the lease."],
        "next_check": "Is renewal, a new lease, or a sale being considered?",
        "would_disprove": ["A documented renewal or long-term hold plan."],
        "pattern_tags": ["LEASE_TERM_TRANSITION"],
    }


def analysis(case_id="case-one", revision="first", conditions=None):
    conditions = conditions or [{"field": "lease_status", "value": "EXPIRED"}]
    observations = [{
        "fact_id": "fact-" + str(index), "field": clause["field"],
        "value": clause["value"], "source_path": "/property/" + clause["field"],
        "source_version": "SYNTHETIC_TEST", "source_snapshot_hash": "synthetic-hash",
        "closed_explanation": False,
    } for index, clause in enumerate(conditions)]
    result = {
        "case_id": case_id, "case_revision": revision,
        "hypotheses": [{
            "hypothesis_id": "hyp-one", "pattern_id": "PROJECT_EXIT_OPTIONS",
            "pattern_tags": ["LEASE_TERM_TRANSITION"],
            "matched_conditions": copy.deepcopy(conditions),
            "supporting_fact_ids": [item["fact_id"] for item in observations],
            "seller_intent": "UNKNOWN", "contact_authorized": False,
        }], "observations": observations,
    }
    result["analysis_id"] = digest(result)
    return result


class InternalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / "private-memory.db")
        self.memory = ReviewMemory(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def review(self, result, event_id="review-one", outcome="USEFUL_INVESTIGATION", **kwargs):
        self.memory.remember_analysis(result)
        return self.memory.review(
            event_id=event_id, analysis_id=result["analysis_id"], hypothesis_id="hyp-one",
            actor="operator", outcome=outcome,
            method="OWNER_DISCLOSURE" if outcome == "SELLER_REASON_CONFIRMED" else "OPERATOR_REVIEW",
            detail="Synthetic private finding retained within local memory.", verified=True,
            **kwargs)

    def test_unverified_pattern_remains_a_saved_draft_and_verified_pattern_activates(self):
        rule = definition()
        draft = self.memory.register_pattern(rule, "operator", "draft-one")
        self.assertFalse(draft["approved"])
        self.assertEqual(self.memory.patterns(), [])
        approved = self.memory.register_pattern(rule, "operator", "approval-one", verified=True)
        self.assertTrue(approved["approved"])
        self.assertEqual(self.memory.patterns(), [rule])
        self.assertEqual(len(self.memory.history("pattern:PROJECT_EXIT_OPTIONS")), 2)

    def test_verified_revision_preserves_old_definition_and_later_draft_cannot_replace_it(self):
        first = definition()
        self.memory.register_pattern(first, "operator", "version-one", verified=True)
        second = copy.deepcopy(first)
        second["conditions"][0]["value"] = "TERMINATED"
        self.memory.register_pattern(second, "operator", "version-two", verified=True)
        third = copy.deepcopy(first)
        third["conditions"][0]["value"] = "PENDING"
        self.memory.register_pattern(third, "operator", "version-three", verified=False)
        self.assertEqual(self.memory.patterns(), [second])
        history = self.memory.history("pattern:PROJECT_EXIT_OPTIONS")
        self.assertEqual([event["data"]["definition"] for event in history], [first, second, third])

    def test_pattern_events_are_idempotent_and_cannot_overwrite_an_approved_rule(self):
        rule = definition()
        self.memory.register_pattern(rule, "operator", "stable-event", verified=True)
        self.memory.register_pattern(rule, "operator", "stable-event", verified=True)
        changed = copy.deepcopy(rule)
        changed["title"] = "Changed title"
        with self.assertRaisesRegex(ValueError, "overwritten"):
            self.memory.register_pattern(changed, "operator", "stable-event", verified=True)
        self.assertEqual(len(self.memory.history("pattern:PROJECT_EXIT_OPTIONS")), 1)

    def test_verified_retirement_deactivates_pattern_and_reactivation_keeps_history(self):
        rule = definition()
        self.memory.register_pattern(rule, "operator", "activation", verified=True)
        retired = self.memory.register_pattern(rule, "operator", "retirement", verified=True, approved=False)
        self.assertFalse(retired["approved"])
        self.assertTrue(retired["verified"])
        self.assertEqual(self.memory.patterns(), [])
        self.memory.register_pattern(rule, "operator", "retirement", verified=True, approved=False)
        self.assertEqual(len(self.memory.history("pattern:PROJECT_EXIT_OPTIONS")), 2)
        with self.assertRaisesRegex(ValueError, "overwritten"):
            self.memory.register_pattern(rule, "operator", "retirement", verified=True, approved=True)
        self.memory.register_pattern(rule, "operator", "reactivation", verified=True, approved=True)
        self.assertEqual(self.memory.patterns(), [rule])
        self.assertEqual(len(self.memory.history("pattern:PROJECT_EXIT_OPTIONS")), 3)

    def test_unverified_retirement_cannot_deactivate_latest_verified_pattern(self):
        rule = definition()
        self.memory.register_pattern(rule, "operator", "activation", verified=True)
        self.memory.register_pattern(rule, "operator", "draft-retirement", verified=False, approved=False)
        self.assertEqual(self.memory.patterns(), [rule])

    def test_registration_takes_an_immutable_snapshot_of_definition(self):
        rule = definition()
        self.memory.register_pattern(rule, "operator", "approval-one", verified=True)
        rule["conditions"][0]["value"] = "MUTATED"
        returned = self.memory.patterns()
        returned[0]["conditions"][0]["value"] = "ANOTHER_MUTATION"
        self.assertEqual(self.memory.patterns()[0]["conditions"][0]["value"], "EXPIRED")

    def test_rule_validation_requires_exact_bounded_fields_and_primitive_conditions(self):
        invalid = []
        for override in [
            {"conditions": []}, {"conditions": [{"field": "lease_status", "value": {"nested": "EXPIRED"}}]},
            {"conditions": [{"field": "lease_status", "value": math.inf}]},
            {"conditions": [{"field": "lease_status", "value": 10 ** 200}]},
            {"conditions": [{"field": "lease_status", "value": ""}]},
            {"pattern_id": "x" * 129}, {"pattern_tags": []}, {"title": ""},
        ]:
            invalid.append({**definition(), **override})
        invalid.append({**definition(), "seller_score": 90})
        bad_clause = copy.deepcopy(definition())
        bad_clause["conditions"][0]["action"] = "send-message"
        invalid.append(bad_clause)
        for index, rule in enumerate(invalid):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                self.memory.register_pattern(rule, "operator", "invalid-" + str(index), verified=True)
        for verified in (1, "true", None):
            with self.subTest(verified=verified), self.assertRaises(ValueError):
                self.memory.register_pattern(definition(), "operator", "boolean", verified=verified)
        for approved in (1, "true", None):
            with self.subTest(approved=approved), self.assertRaises(ValueError):
                self.memory.register_pattern(definition(), "operator", "approval-boolean", approved=approved)
        self.assertEqual(self.memory.patterns(), [])

    def test_controls_identity_demographic_and_url_fields_cannot_be_learned_rules(self):
        for field in ("seller_intent", "contact_authorized", "owner_name", "age", "children",
                      "marital_status", "divorce", "death", "financial_distress", "source_url",
                      "https://example.test", "command", "action_send_message", "age_group",
                      "owner_age", "birth_year", "date_of_birth", "family_size", "number_of_children",
                      "raw_quote", "public_statement_text", "context_tags", "overall_rank",
                      "ageGroup", "dateOfBirth", "numberOfChildren", "ownerName"):
            rule = definition()
            rule["conditions"] = [{"field": field, "value": "SYNTHETIC"}]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.memory.register_pattern(rule, "operator", "blocked-" + field, verified=True)

    def test_location_price_equity_or_statement_context_alone_cannot_qualify_a_property(self):
        for field in ("city", "market_code", "price", "estimated_equity", "assessment_total",
                      "assessment_land_share", "living_sqft", "year_built", "acres", "mortgage_balance"):
            rule = definition()
            rule["conditions"] = [{"field": field, "value": "SYNTHETIC"}]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "alone"):
                self.memory.register_pattern(rule, "operator", "context-" + field, verified=True)
        rule = definition()
        rule["conditions"].append({"field": "city", "value": "SYNTHETIC TOWN"})
        self.memory.register_pattern(rule, "operator", "location-context", verified=True)
        self.assertEqual(self.memory.patterns(), [rule])

    def test_sensitive_token_validation_does_not_mistake_mortgage_for_age(self):
        rule = definition()
        rule["conditions"] = [{"field": "mortgage_record_status", "value": "RELEASED"}]
        self.memory.register_pattern(rule, "operator", "mortgage-fact", verified=True)
        self.assertEqual(self.memory.patterns(), [rule])

    def test_examples_only_use_verified_reviews_and_preserve_exact_snapshot_refs(self):
        result = analysis()
        self.review(result)
        self.memory.review(event_id="unverified-newer", analysis_id=result["analysis_id"],
            hypothesis_id="hyp-one", actor="operator", outcome="FALSE_POSITIVE",
            method="OPERATOR_REVIEW", detail="Unverified possibility.", verified=False)
        example = self.memory.examples(["LEASE_TERM_TRANSITION"])[0]
        self.assertEqual(example["snapshot_reference"], {
            "analysis_id": result["analysis_id"], "case_id": "case-one", "case_revision": "first",
            "hypothesis_id": "hyp-one", "review_event_id": "review-one"})
        self.assertEqual(example["matched_conditions"], result["hypotheses"][0]["matched_conditions"])
        self.assertEqual(example["supporting_observations"], result["observations"])
        self.assertEqual(example["review"]["outcome"], "USEFUL_INVESTIGATION")
        self.assertEqual(self.memory.examples(["UNRELATED_TAG"]), [])

    def test_latest_verified_review_per_property_and_pattern_is_comparable_example(self):
        first = analysis()
        self.review(first, "first-review", "FALSE_POSITIVE")
        second = analysis(revision="second")
        self.review(second, "second-review", "SELLER_REASON_CONFIRMED")
        examples = self.memory.examples()
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["snapshot_reference"]["analysis_id"], second["analysis_id"])
        self.assertEqual(examples[0]["review"]["outcome"], "SELLER_REASON_CONFIRMED")
        self.assertEqual(examples[0]["hypothesis"]["seller_intent"], "UNKNOWN")
        self.assertEqual(len(self.memory.history("case-one")), 4)

    def test_verified_correction_preserves_original_event_but_updates_comparable_outcome(self):
        result = analysis()
        self.review(result, "old-review", "FALSE_POSITIVE")
        self.review(result, "correction", "USEFUL_INVESTIGATION", supersedes="old-review")
        self.assertEqual(self.memory.examples()[0]["review"]["event_id"], "correction")
        self.assertEqual(len(self.memory.history("case-one")), 3)

    def test_suggestions_count_distinct_properties_and_never_activate_themselves(self):
        self.review(analysis(), "review-one", "USEFUL_INVESTIGATION")
        self.review(analysis(revision="new"), "review-one-again", "USEFUL_INVESTIGATION")
        self.review(analysis(case_id="case-two"), "review-two", "FALSE_POSITIVE")
        suggestion = self.memory.suggest_patterns()[0]
        self.assertEqual(suggestion["reviewed_properties"], 2)
        self.assertEqual(suggestion["outcomes"], {"FALSE_POSITIVE": 1, "USEFUL_INVESTIGATION": 1})
        self.assertFalse(suggestion["approved"])
        self.assertFalse(suggestion["adopted"])
        self.assertEqual(len(suggestion["examples"]), 2)
        self.assertEqual(self.memory.patterns(), [])
        self.assertEqual(self.memory.lessons()[0]["reviewed_properties"], 2)

    def test_unreferenced_or_closed_fact_cannot_teach_a_condition(self):
        result = analysis()
        result["hypotheses"][0]["matched_conditions"].append({"field": "project_status", "value": "COMPLETED"})
        result["observations"][0]["closed_explanation"] = True
        result["analysis_id"] = digest({key: value for key, value in result.items() if key != "analysis_id"})
        self.review(result)
        self.assertEqual(self.memory.examples()[0]["matched_conditions"], [])
        self.assertEqual(self.memory.suggest_patterns(), [])

    def test_context_only_evidence_is_retained_but_not_suggested_as_a_qualifying_rule(self):
        result = analysis(conditions=[{"field": "city", "value": "SYNTHETIC TOWN"}])
        self.review(result)
        self.assertEqual(len(self.memory.examples()[0]["matched_conditions"]), 1)
        self.assertEqual(self.memory.suggest_patterns(), [])

    def test_observation_explicitly_unusable_for_pattern_is_kept_but_not_learned(self):
        result = analysis()
        result["observations"][0]["usable_for_pattern"] = False
        result["analysis_id"] = digest({key: value for key, value in result.items() if key != "analysis_id"})
        self.review(result)
        example = self.memory.examples()[0]
        self.assertEqual(example["matched_conditions"], [])
        self.assertEqual(example["supporting_observations"], result["observations"])
        self.assertEqual(self.memory.suggest_patterns(), [])

    def test_analysis_and_examples_remain_immutable_after_returned_values_change(self):
        result = analysis()
        self.review(result)
        example = self.memory.examples()[0]
        example["supporting_observations"][0]["value"] = "MUTATED"
        self.assertEqual(self.memory.analysis(result["analysis_id"])["observations"][0]["value"], "EXPIRED")
        self.assertEqual(self.memory.examples()[0]["supporting_observations"][0]["value"], "EXPIRED")
        changed = copy.deepcopy(result)
        changed["observations"][0]["value"] = "MUTATED"
        with self.assertRaisesRegex(ValueError, "content"):
            self.memory.remember_analysis(changed)

    def test_comparable_retrieval_does_not_recursively_copy_prior_example_trees(self):
        result = analysis()
        result["hypotheses"][0]["comparable_reviewed_cases"] = [{"nested": "old derived retrieval"}]
        result["hypotheses"][0]["reviewed_pattern_lessons"] = [{"pattern": "old derived lesson"}]
        result["analysis_id"] = digest({key: value for key, value in result.items() if key != "analysis_id"})
        self.review(result)
        retrieved = self.memory.examples()[0]["hypothesis"]
        self.assertNotIn("comparable_reviewed_cases", retrieved)
        self.assertNotIn("reviewed_pattern_lessons", retrieved)
        self.assertIn("comparable_reviewed_cases", self.memory.analysis(result["analysis_id"])["hypotheses"][0])

    def test_examples_limit_and_tag_filters_are_bounded(self):
        for limit in (0, 201, True, "20"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.memory.examples(limit=limit)
        with self.assertRaises(ValueError):
            self.memory.examples([""])

    def test_postgres_adapter_does_not_create_or_migrate_tables(self):
        queries = []

        class Connection:
            def execute(self, query):
                queries.append(query)

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        fake = types.SimpleNamespace(connect=lambda dsn: Connection())
        with patch.dict("sys.modules", {"psycopg": fake}):
            store = ReviewMemory.postgres_store("SYNTHETIC_NOT_A_LIVE_DSN")
        self.assertTrue(store.postgres)
        self.assertEqual(queries, ["SELECT record_key FROM pmi_ai_review_records LIMIT 1"])


if __name__ == "__main__":
    unittest.main()
