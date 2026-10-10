import copy
from pathlib import Path
import tempfile
import unittest

from seller_ai import analyze, prepare_packets
from seller_ai_memory import ReviewMemory
from test_seller_ai import snapshot


class ReasoningStability(unittest.TestCase):
    def hold(self, memory, payload):
        result = analyze(prepare_packets(payload)[0], memory)
        memory.review(event_id="negative", analysis_id=result["analysis_id"],
            hypothesis_id=result["hypotheses"][0]["hypothesis_id"], actor="operator",
            outcome="FALSE_POSITIVE", method="OPERATOR_REVIEW",
            detail="The supplied project inquiry was already disproved.", verified=True)
        return result

    def test_route_order_does_not_reopen_identical_disproved_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ReviewMemory(str(Path(directory) / "memory.db"))
            payload = snapshot()
            routes = payload["profiles"][0]["why_pmi_noticed_it"]
            routes.append({"route": "OTHER_CONTEXT", "state": "CONTEXT_ONLY_NOT_QUALIFYING",
                           "actual_values": {"administrative_reference": "SYNTHETIC"}})
            first = self.hold(memory, payload)
            reordered = copy.deepcopy(payload)
            reordered["profiles"][0]["why_pmi_noticed_it"].reverse()
            result = analyze(prepare_packets(reordered)[0], memory)
            self.assertEqual(first["case_revision"], result["case_revision"])
            self.assertEqual(first["hypotheses"][0]["hypothesis_id"], result["hypotheses"][0]["hypothesis_id"])
            self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])

    def test_duplicate_copy_of_one_route_does_not_reopen_disproved_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ReviewMemory(str(Path(directory) / "memory.db"))
            payload = snapshot()
            first = self.hold(memory, payload)
            copied = copy.deepcopy(payload)
            copied["profiles"][0]["why_pmi_noticed_it"].append(copy.deepcopy(
                copied["profiles"][0]["why_pmi_noticed_it"][0]))
            result = analyze(prepare_packets(copied)[0], memory)
            self.assertEqual(first["hypotheses"][0]["evidence_fingerprint"], result["hypotheses"][0]["evidence_fingerprint"])
            self.assertFalse(result["hypotheses"][0]["operator_review_eligible"])

    def test_new_dated_source_observation_can_reconsider_old_support(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ReviewMemory(str(Path(directory) / "memory.db"))
            payload = snapshot()
            values = payload["profiles"][0]["why_pmi_noticed_it"][0]["actual_values"]
            values.update(source_record_id="SYNTHETIC-INSPECTION-ONE", inspection_date="2026-09-01")
            first = self.hold(memory, payload)
            revised = copy.deepcopy(payload)
            revised["profiles"][0]["why_pmi_noticed_it"][0]["actual_values"].update(
                source_record_id="SYNTHETIC-INSPECTION-TWO", inspection_date="2026-10-10")
            result = analyze(prepare_packets(revised)[0], memory)
            self.assertNotEqual(first["hypotheses"][0]["evidence_fingerprint"], result["hypotheses"][0]["evidence_fingerprint"])
            self.assertTrue(result["hypotheses"][0]["operator_review_eligible"])
            self.assertEqual(result["seller_intent"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
