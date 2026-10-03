#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18T"
def build_v18t():
 x=json.loads((Path(__file__).with_name("v18t_donor.json")).read_text())["candidates"]
 counts={}
 for a in x:
  k=a["chronology_integrity_disposition"]; counts[k]=counts.get(k,0)+1
 g=[a for a in x if a["v18g_disposition"] is not None]
 return {"status":"ok","version":VERSION,
 "mode":"V18G_CHRONOLOGY_INTEGRITY_CROSSCHECK_EXACT_113_READ_ONLY",
 "summary":{"candidate_properties":len(x),"v18g_chronology_jobs_integrated":len(g),
 "chronology_integrity_counts":counts,
 "research_continues_for_all":all(a["research_may_continue"] for a in x),"database_writes":0},
 "purpose":"Integrate the exact proven V18G chronology dispositions into the protected 113-candidate lane so historical episodes are not misread as current factual relationships.",
 "chronology_integrity":x,
 "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
 "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
