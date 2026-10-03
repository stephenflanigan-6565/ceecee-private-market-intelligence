#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18P"
def build_v18p():
 r=json.loads((Path(__file__).with_name("v18p_donor.json")).read_text())["active_results"]
 d={}; rem=[]; resolved=[]
 for x in r:
  d[x["disposition"]]=d.get(x["disposition"],0)+1
  (rem if x["disposition"]=="EXTERNAL_VERIFICATION_REMAINS" else resolved).append(x)
 return {"status":"ok","version":VERSION,"mode":"MEMORY_FIRST_ACTIVE_INVESTIGATION_RESOLUTION_EXACT_V18O_23_READ_ONLY",
 "summary":{"v18o_active_investigations":len(r),"disposition_counts":d,
 "resolved_from_existing_memory":len(resolved),"external_verification_remaining":len(rem),
 "research_continues_for_all_active":all(x["research_may_continue"] for x in r),"database_writes":0},
 "purpose":"Work only the V18O active 23, resolve discriminators from locked evidence where supported, and isolate the exact external-verification remainder.",
 "resolved_from_memory":resolved,"external_verification_queue":rem,"active_results":r,
 "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
 "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
