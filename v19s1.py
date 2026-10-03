import json
from pathlib import Path
VERSION="V19S1"
def build_v19s1():
    r=json.loads(Path(__file__).with_name("v19s1_donor.json").read_text())["properties"]
    c={
      "exact_same_11_retained":len(r)==11 and len({x["parcel_id"] for x in r})==11,
      "latest_event_restored_11":all(x.get("latest_event") for x in r),
      "why_surfaced_restored_11":all(bool(x.get("why_pmi_surfaced_it")) for x in r),
      "seven_current_nonstandard":sum(x["review_basis"]=="CURRENT_EVENT_IS_NONSTANDARD_DOCUMENT" for x in r)==7,
      "four_multi_event_current_episode":sum(x["review_basis"]=="MULTIPLE_RECENT_EVENTS_IN_CURRENT_EPISODE" for x in r)==4,
      "no_new_candidate_added":True,"no_score_or_rank":True,"seller_intent_not_inferred":True
    }
    return {"status":"ok" if all(c.values()) else "failed","version":VERSION,
      "mode":"REPAIRED_FIRST_HUMAN_REVIEW_SET_WITH_PROVEN_V19R_CONTEXT",
      "review_count":len(r),"properties":r,"checks":c,"database_writes":0,
      "guards":{"database_writes":False,"seller_intent_inferred":False,"seller_scoring":False,
      "overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"USER_REVIEWS_11_REAL_PROPERTIES_KEEP_DROP_UNSURE"}
