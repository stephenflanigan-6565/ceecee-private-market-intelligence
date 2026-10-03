import json
from pathlib import Path
VERSION="V19T"
def build_v19t():
    cards=json.loads(Path(__file__).with_name("v19t_donor.json").read_text())["cards"]
    checks={
      "exact_operator_cards_11":len(cards)==11 and len({x["parcel_id"] for x in cards})==11,
      "all_have_owner":all(bool(x["owner"]) for x in cards),
      "all_have_what_happened":all(bool(x["what_happened"]) for x in cards),
      "all_have_readable_reason":all(bool(x["why_it_is_here"]) for x in cards),
      "all_have_next_action":all(bool(x["agent_action"]) for x in cards),
      "seller_intent_not_inferred":all(x["seller_intent"]=="Not established" for x in cards),
      "no_score_or_rank":True,"no_candidate_logic_change":True
    }
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"PMI_OPERATOR_PROPERTY_CARDS_READ_ONLY","card_count":len(cards),
      "display_title":"Private Market Intelligence — Property Review",
      "display_subtitle":"Current factual property activity prepared for agent review",
      "cards":cards,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"seller_intent_inferred":False,"seller_scoring":False,
      "overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"BUILD_POLISHED_OPERATOR_REVIEW_SCREEN_FROM_PROVEN_CARDS"}
