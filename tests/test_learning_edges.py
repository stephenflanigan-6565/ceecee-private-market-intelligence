import copy
from pathlib import Path
import tempfile
import unittest

from seller_ai import analyze, prepare_packets
from seller_ai_memory import ReviewMemory
from test_seller_ai import ScriptedReasoner, snapshot


class LearningEdges(unittest.TestCase):
    def test_shared_owner_context_is_a_reported_name_link_not_identity_or_motive_proof(self):
        payload = snapshot()
        other = copy.deepcopy(payload["profiles"][0])
        other.update(parcel_id="SECOND-PARCEL", property_address="2 SYNTHETIC TEST RD")
        payload["profiles"].append(other)
        payload["profile_payload"] = {"complete": True, "returned": 2, "total": 2}
        packets = prepare_packets(payload)
        self.assertEqual(len(packets), 2)
        for packet in packets:
            relation = packet["related_property_context"][0]
            self.assertEqual(relation["relationship"], "SHARED_REPORTED_NAME_NOT_VERIFIED_CONTROL")
            self.assertEqual(len(relation["other_case_ids"]), 1)
            self.assertNotIn(packet["case_id"], relation["other_case_ids"])

    def test_known_identity_text_inside_source_prose_is_redacted_for_model_calls(self):
        payload = snapshot()
        payload["profiles"][0]["why_pmi_noticed_it"][0]["actual_values"]["source_note"] = (
            "SYNTHETIC PRIVATE OWNER reported work at 1 SYNTHETIC TEST RD.")
        client = ScriptedReasoner()
        analyze(prepare_packets(payload)[0], client)
        self.assertNotIn("SYNTHETIC PRIVATE OWNER", str(client.calls))
        self.assertNotIn("1 SYNTHETIC TEST RD", str(client.calls))

    def test_repeated_analyses_of_one_property_do_not_inflate_pattern_learning(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ReviewMemory(str(Path(directory) / "review.db"))
            packet = prepare_packets(snapshot())[0]
            for index in range(3):
                analysis = analyze(packet, ScriptedReasoner(), memory)
                memory.review(event_id="event-" + str(index),
                    analysis_id=analysis["analysis_id"], hypothesis_id="H1",
                    actor="operator", outcome="USEFUL_INVESTIGATION",
                    method="OPERATOR_REVIEW", detail="Synthetic completed project warranted inquiry.",
                    verified=True)
            self.assertEqual(memory.lessons()[0]["reviewed_properties"], 1)
            self.assertEqual(memory.lessons()[0]["outcomes"], {"USEFUL_INVESTIGATION": 1})
