#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18O"
def build_v18o():
 c=json.loads((Path(__file__).with_name("v18o_donor.json")).read_text())["candidates"]; disp={}; cats={}; active=[]
 for x in c:
  d=x["v18o_discrimination"]["disposition"]; disp[d]=disp.get(d,0)+1
  k=x["operational_category"]; cats[k]=cats.get(k,0)+1
  if d=="ACTIVE_FACTUAL_INVESTIGATION": active.append({"parcel_id":x["parcel_id"],"episode_lane":x["episode_classification"]["lane"],"operational_category":x["operational_category"],"questions":x["v18o_discrimination"]["specific_discriminating_questions"],"followup_requirements":x["open_followup_requirements"]})
 return {"status":"ok","version":VERSION,"mode":"FACTUAL_DISCRIMINATOR_RESEARCH_COMPRESSION_EXACT_V18N_113_READ_ONLY","summary":{"candidate_properties":len(c),"v18n_current_context_properties":sum(1 for x in c if x["episode_classification"]["lane"].startswith("CURRENT_")),"disposition_counts":disp,"active_factual_investigation_properties":len(active),"operational_category_counts":cats,"research_continues_for_all_candidates":all(x["v18o_discrimination"]["research_may_continue"] for x in c),"database_writes":0},"purpose":"Compress current factual cases into a smaller active-investigation lane only where a specific unresolved discriminator remains; preserve all other candidates and follow-up cases.","active_investigation_set":active,"candidates":c,"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
