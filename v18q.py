#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18Q"
def build_v18q():
 j=json.loads((Path(__file__).with_name("v18q_donor.json")).read_text())["verification_jobs"]
 routes={}; missing={}; ids=0; relationship=0
 for x in j:
  ids+=x["unresolved_identity_count"]
  relationship+=1 if x["relationship_analysis_needed_after_metadata"] else 0
  for y in x["unresolved_source_identities"]:
   for f in y["missing_fields"]: missing[f]=missing.get(f,0)+1
  for r in x["verification_routes"]:
   routes[r["route"]]=routes.get(r["route"],0)+1
 return {"status":"ok","version":VERSION,
 "mode":"EXACT_EXTERNAL_VERIFICATION_ROUTER_V18P_8_READ_ONLY",
 "summary":{"external_verification_properties":len(j),"unresolved_source_identities":ids,
 "missing_field_counts":missing,"relationship_analysis_after_metadata":relationship,
 "route_counts":routes,"research_continues_for_all":all(x["research_may_continue"] for x in j),
 "database_writes":0},
 "purpose":"Convert the exact V18P external-verification remainder into parcel/source/field-specific machine and manual verification routes.",
 "verification_jobs":j,
 "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
 "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
