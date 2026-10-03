#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18V"
def build_v18v():
 x=json.loads((Path(__file__).with_name("v18v_donor.json")).read_text())["routes"]
 counts={}
 for a in x: counts[a["research_value_route"]]=counts.get(a["research_value_route"],0)+1
 return {"status":"ok","version":VERSION,
 "mode":"RESEARCH_VALUE_SOURCE_STRATEGY_EXACT_V18U_39_READ_ONLY",
 "summary":{"open_factual_discriminator_properties":len(x),"route_counts":counts,
 "manual_exhausted_properties":sum(1 for a in x if a["research_value_route"]=="MANUAL_AUTHORITATIVE_VERIFICATION_EXHAUSTED_AUTOMATION"),
 "automatic_lookup_potential_value_properties":sum(1 for a in x if a["automatic_lookup_has_potential_value"]),
 "research_continues_for_all":all(a["research_may_continue"] for a in x),"database_writes":0},
 "purpose":"Choose an evidence-acquisition strategy for each exact V18U open discriminator so PMI does not repeat exhausted searches or confuse unknown facts with automatic re-query instructions.",
 "research_value_routes":x,
 "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
 "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
