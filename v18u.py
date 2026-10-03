#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18U"
def build_v18u():
 x=json.loads((Path(__file__).with_name("v18u_donor.json")).read_text())["profiles"]
 counts={}
 for a in x:
  counts[a["evidence_value_state"]]=counts.get(a["evidence_value_state"],0)+1
 openx=[a for a in x if a["additional_research_needed_now"]]
 return {"status":"ok","version":VERSION,
 "mode":"EVIDENCE_VALUE_AND_NEXT_FACT_INTELLIGENCE_EXACT_V18T_113_READ_ONLY",
 "summary":{"candidate_properties":len(x),"evidence_value_state_counts":counts,
 "open_factual_discriminator_properties":len(openx),
 "history_separated_properties":sum(1 for a in x if a["history_separated_from_current"]),
 "properties_with_material_next_fact":sum(1 for a in x if a["material_next_fact"] is not None),
 "research_continues_for_all":all(a["research_may_continue"] for a in x),"database_writes":0},
 "purpose":"Distinguish explained factual context from genuinely open factual discriminators and identify the next fact that could materially change understanding, without scoring or seller inference.",
 "evidence_value_profiles":x,
 "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
 "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
