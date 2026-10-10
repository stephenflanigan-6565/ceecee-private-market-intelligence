import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

from seller_ai import OpenAIReasoner, analyze, prepare_packets
from seller_ai_memory import ReviewMemory


def snapshot(address="1 SYNTHETIC TEST RD", parcel="TEST-PARCEL"):
    return {
        "status": "ok", "version": "FIND4",
        "profile_payload": {"complete": True, "returned": 1, "total": 1},
        "profiles": [{
            "parcel_id": parcel, "property_address": address,
            "owner_identity": {"names": ["SYNTHETIC PRIVATE OWNER"]},
            "why_pmi_noticed_it": [{
                "route": "PROJECT_CONTEXT",
                "state": "ACTIVE_RESEARCH_ROUTE",
                "actual_values": {"project_status": "COMPLETED", "current_use": "VACANT"},
            }],
            "seller_intent": "UNKNOWN", "contact_authorized": False,
        }],
    }


class ScriptedReasoner:
    model = "TEST_ONLY_NO_MODEL_CALL"

    def __init__(self, decision="INVESTIGATE", support="SUPPORTED", no_facts=False):
        self.calls = []
        self.decision, self.support, self.no_facts = decision, support, no_facts

    def complete(self, stage, system, context, schema):
        self.calls.append({"stage": stage, "context": copy.deepcopy(context), "system": system})
        if stage == "propose":
            ids = [] if self.no_facts else [
                item["fact_id"] for item in context["observations"]
                if item["value"] in ("COMPLETED", "VACANT")]
            return {"hypotheses": [{
                "hypothesis_id": "H1", "title": "Project completion with an unused property",
                "circumstance": "The supplied observations show completed work and a vacant use.",
                "opportunity": "Clarify whether a completed project is ready for disposition.",
                "possible_seller_reason": "An exit after project completion is a hypothesis.",
                "agent_help": "Offer a sale-versus-hold plan tied to the owner's actual objective.",
                "supporting_fact_ids": ids,
                "alternative_explanations": ["The owner may be preparing to occupy or rent it."],
                "next_check": "Is the completed property being held, leased, occupied, or sold?",
                "would_disprove": ["A documented long-term hold or occupancy plan."],
                "pattern_tags": ["COMPLETED_PROJECT_UNUSED_PROPERTY"],
            }]}
        proposal = context["proposals"]["hypotheses"][0]
        return {"reviews": [{
            "hypothesis_id": "H1", "decision": self.decision, "support": self.support,
            "supporting_fact_ids": proposal["supporting_fact_ids"],
            "reason": "The scenario is property-specific; its owner's intended exit remains unverified.",
        }]}


class BrainTests(unittest.TestCase):
    def packet(self, **kwargs):
        return prepare_packets(snapshot(**kwargs))[0]

    def test_packets_preserve_case_and_partial_scope_without_requiring_a_fixed_list(self):
        payload = snapshot()
        payload["profile_payload"] = {"complete": False, "returned": 1, "total": 194}
        packet = prepare_packets(payload)[0]
        self.assertFalse(packet["coverage"]["source_exports"][0]["complete_export_established"])
        self.assertEqual(packet["coverage"]["hypothesis_vocabulary"], "EXPANDABLE")
        self.assertFalse(packet["coverage"]["finalized_seller_reason_list_required"])

    def test_grounded_unknown_owner_can_get_a_focused_inquiry_not_confirmed_intent(self):
        payload = snapshot()
        payload["profiles"][0]["owner_identity"]["names"] = []
        result = analyze(prepare_packets(payload)[0], ScriptedReasoner())
        hypothesis = result["hypotheses"][0]
        self.assertTrue(hypothesis["operator_review_eligible"])
        self.assertEqual(hypothesis["seller_intent"], "UNKNOWN")
        self.assertFalse(hypothesis["contact_authorized"])
        self.assertEqual(result["property_address"], "1 SYNTHETIC TEST RD")

    def test_model_context_omits_owner_names_and_property_address(self):
        client = ScriptedReasoner()
        analyze(self.packet(), client)
        for call in client.calls:
            text = json.dumps(call["context"])
            self.assertNotIn("SYNTHETIC PRIVATE OWNER", text)
            self.assertNotIn("1 SYNTHETIC TEST RD", text)
        self.assertEqual([call["stage"] for call in client.calls], ["propose", "challenge"])

    def test_model_cannot_promote_a_no_evidence_idea(self):
        result = analyze(self.packet(), ScriptedReasoner(no_facts=True))
        self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])
        self.assertEqual(result["hypotheses"][0]["disposition"], "MACHINE_RESEARCH")

    def test_contradicted_or_rejected_explanation_is_kept_out_of_review(self):
        for decision, support in [("REJECT", "CONTRADICTED"), ("INVESTIGATE", "UNCLEAR")]:
            with self.subTest(decision=decision, support=support):
                result = analyze(self.packet(), ScriptedReasoner(decision, support))
                self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])

    def test_missing_address_does_not_erase_hypothesis_but_holds_address_handoff(self):
        result = analyze(self.packet(address=None), ScriptedReasoner())
        self.assertEqual(len(result["hypotheses"]), 1)
        self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])

    def test_fabricated_observation_is_rejected_before_challenge_or_memory(self):
        class FabricatingClient(ScriptedReasoner):
            def complete(self, stage, *args):
                result = super().complete(stage, *args)
                if stage == "propose":
                    result["hypotheses"][0]["supporting_fact_ids"] = ["INVENTED_FACT"]
                return result
        client = FabricatingClient()
        with self.assertRaisesRegex(ValueError, "absent"):
            analyze(self.packet(), client)
        self.assertEqual(len(client.calls), 1)

    def test_critic_cannot_invent_more_support(self):
        class FabricatingCritic(ScriptedReasoner):
            def complete(self, stage, *args):
                result = super().complete(stage, *args)
                if stage == "challenge":
                    result["reviews"][0]["supporting_fact_ids"] = ["INVENTED_FACT"]
                return result
        with self.assertRaisesRegex(ValueError, "uncited"):
            analyze(self.packet(), FabricatingCritic())

    def test_missing_challenge_cannot_silently_promote_a_proposal(self):
        class IncompleteClient(ScriptedReasoner):
            def complete(self, stage, *args):
                return {"reviews": []} if stage == "challenge" else super().complete(stage, *args)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            analyze(self.packet(), IncompleteClient())

    def test_closed_history_does_not_globally_exclude_an_independent_hypothesis(self):
        payload = snapshot()
        payload["profiles"][0]["why_pmi_noticed_it"] = [{
            "route": "ASSESSMENT_VALUE_CONTEXT",
            "state": "EXPLAINED_ROUTE_CLOSED",
            "actual_values": {"assessment_timing": "Administrative cycle explains the value change"},
        }]
        payload["profiles"][0]["project_context"] = {
            "project_status": "COMPLETED", "current_use": "VACANT",
        }
        packet = prepare_packets(payload)[0]
        before = copy.deepcopy(packet["prior_route_decisions"])
        result = analyze(packet, ScriptedReasoner())
        self.assertEqual(packet["prior_route_decisions"], before)
        self.assertTrue(result["hypotheses"][0]["operator_review_eligible"])
        self.assertEqual(result["seller_intent"], "UNKNOWN")

    def test_reviewed_outcome_is_retrieved_but_not_borrowed_as_another_sellers_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ReviewMemory(str(Path(directory) / "memory.db"))
            first = analyze(self.packet(), ScriptedReasoner(), memory)
            memory.review(event_id="review-1", analysis_id=first["analysis_id"],
                hypothesis_id="H1", actor="operator", outcome="SELLER_REASON_CONFIRMED",
                method="OWNER_DISCLOSURE", detail="Synthetic owner said the completed project was for sale.",
                verified=True)
            client = ScriptedReasoner()
            second = analyze(self.packet(parcel="OTHER-PARCEL"), client, memory)
            lessons = client.calls[0]["context"]["reviewed_pattern_lessons"]
            self.assertEqual(lessons[0]["outcomes"]["SELLER_REASON_CONFIRMED"], 1)
            self.assertEqual(second["seller_intent"], "UNKNOWN")
            self.assertNotIn("Synthetic owner said", json.dumps(client.calls))


class ProviderTests(unittest.TestCase):
    def test_explicit_model_call_uses_structured_outputs_and_no_server_storage(self):
        calls = []
        def transport(request, timeout):
            calls.append((request, timeout))
            return io.BytesIO(json.dumps({"status": "completed", "output": [{
                "content": [{"type": "output_text", "text": '{"hypotheses":[]}'}]
            }]}).encode())
        client = OpenAIReasoner("SYNTHETIC_TEST_KEY", "chosen-model", transport=transport)
        self.assertEqual(client.complete("propose", "instructions", {"case": "test"}, {}),
                         {"hypotheses": []})
        request, timeout = calls[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertFalse(body["store"])
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(body["model"], "chosen-model")
        self.assertEqual(timeout, 25)

    def test_incomplete_and_refused_responses_do_not_create_a_result(self):
        for data in [
            {"status": "incomplete", "output": []},
            {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]},
        ]:
            with self.subTest(data=data):
                client = OpenAIReasoner("test", "model", transport=lambda *a, **k:
                    io.BytesIO(json.dumps(data).encode()))
                with self.assertRaises(ValueError):
                    client.complete("propose", "test", {}, {})

    def test_provider_errors_do_not_expose_credentials_or_response_bodies(self):
        def transport(request, **kwargs):
            raise urllib.error.HTTPError(request.full_url, 401, "SENSITIVE_PROVIDER_BODY", {}, None)
        client = OpenAIReasoner("SYNTHETIC_SECRET", "model", transport=transport)
        with self.assertRaises(RuntimeError) as raised:
            client.complete("propose", "test", {}, {})
        self.assertNotIn("SYNTHETIC_SECRET", str(raised.exception))
        self.assertNotIn("SENSITIVE_PROVIDER_BODY", str(raised.exception))


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / "memory.db")
        self.memory = ReviewMemory(self.path)
        self.analysis = analyze(prepare_packets(snapshot())[0], ScriptedReasoner(), self.memory)
        self.review = dict(event_id="event-1", analysis_id=self.analysis["analysis_id"],
                          hypothesis_id="H1", actor="operator", outcome="FALSE_POSITIVE",
                          method="OPERATOR_REVIEW", detail="The owner intended occupancy.",
                          verified=True)

    def tearDown(self):
        self.directory.cleanup()

    def test_memory_survives_reopening_and_preserves_original_reasoning(self):
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

    def test_same_feedback_identifier_cannot_overwrite_an_old_finding(self):
        self.memory.review(**self.review)
        with self.assertRaisesRegex(ValueError, "overwritten"):
            self.memory.review(**{**self.review, "detail": "Different finding."})
        self.assertEqual(self.memory.lessons()[0]["outcomes"], {"FALSE_POSITIVE": 1})

    def test_verified_correction_retains_history_and_updates_lessons(self):
        self.memory.review(**self.review)
        self.memory.review(**{**self.review, "event_id": "event-2",
            "outcome": "USEFUL_INVESTIGATION", "detail": "Later review found a legitimate exit opportunity.",
            "supersedes": "event-1"})
        self.assertEqual(len(self.memory.history(self.analysis["case_id"])), 3)
        self.assertEqual(self.memory.lessons()[0]["outcomes"], {"USEFUL_INVESTIGATION": 1})

    def test_unverified_feedback_is_saved_without_influencing_later_reasoning(self):
        self.memory.review(**{**self.review, "verified": False})
        self.assertEqual(self.memory.lessons(), [])
        self.assertEqual(len(self.memory.history(self.analysis["case_id"])), 2)

    def test_reviewer_opinion_cannot_be_recorded_as_owner_disclosure(self):
        with self.assertRaisesRegex(ValueError, "owner"):
            self.memory.review(**{**self.review, "outcome": "SELLER_REASON_CONFIRMED"})

    def test_unknown_analysis_hypothesis_and_correction_are_rejected(self):
        for override in [
            {"analysis_id": "unknown"},
            {"hypothesis_id": "unknown"},
            {"supersedes": "unknown"},
        ]:
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.memory.review(**{**self.review, **override})

    def test_modified_analysis_cannot_replace_its_original_snapshot(self):
        changed = copy.deepcopy(self.analysis)
        changed["hypotheses"][0]["circumstance"] = "Different facts."
        with self.assertRaisesRegex(ValueError, "content"):
            self.memory.remember_analysis(changed)


if __name__ == "__main__":
    unittest.main()
