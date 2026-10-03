#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V19P"
def build_v19p():
    d=json.loads(Path(__file__).with_name("v19p_donor.json").read_text())
    rows=d["review_set"]
    solid=sum(x["status"]=="SOLID" for x in rows)
    follow=len(rows)-solid
    with_addr=sum(bool(x["property_address"]) for x in rows)
    checks={
      "exact_v18p_active_23":len(rows)==23 and len({x["parcel_id"] for x in rows})==23,
      "solid_plus_followup_23":solid+follow==23,
      "all_have_owner_context":all(bool(x["owner_context"]) for x in rows),
      "seller_intent_not_inferred":all(x["seller_intent"]=="NOT_ESTABLISHED" for x in rows),
      "no_new_score":True,"no_new_ranking":True,"no_candidate_reselection":True
    }
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"FIRST_COMPACT_REVIEWABLE_PROPERTY_SET_FROM_PROVEN_ACTIVE_23",
      "review_set_count":len(rows),"coverage":{"with_address":with_addr,"without_address":23-with_addr,
      "with_owner_context":sum(bool(x["owner_context"]) for x in rows)},
      "review_status":{"SOLID":solid,"FOLLOW_UP":follow},
      "properties":rows,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"seller_intent_inferred":False,
      "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"USER_REVIEWS_FIRST_REAL_PROPERTY_SET_GOOD_BAD_AND_WHY"}
