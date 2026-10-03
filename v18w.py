#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18W"
def build_v18w():
 x=json.loads((Path(__file__).with_name("v18w_donor.json")).read_text())["cases"]
 counts={}
 for a in x: counts[a["source_strategy"]]=counts.get(a["source_strategy"],0)+1
 return {"status":"ok","version":VERSION,
 "mode":"SOURCE_SPECIFIC_INFORMATION_VALUE_EXACT_V18V_3_READ_ONLY",
 "summary":{"source_value_review_properties":len(x),"source_strategy_counts":counts,
 "automated_acquisition_warranted_properties":sum(1 for a in x if a["automated_acquisition_warranted"]),
 "historical_metadata_only_properties":sum(1 for a in x if a["historical_metadata_gap_only"]),
 "research_continues_for_all":True,"database_writes":0},
 "purpose":"Resolve the exact V18V three-case source-value review into source-specific evidence strategies, distinguishing genuinely refreshable current uncertainty from old metadata gaps that should not trigger broad automated searches.",
 "source_value_cases":x,
 "guards":{"database_writes":False,"external_calls":False,"investigate_state_touched":False,
 "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
 "contact_authorized":False,"outreach_touched":False}}
