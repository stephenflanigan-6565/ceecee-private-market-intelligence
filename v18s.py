#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18S"
def build_v18s():
 x=json.loads((Path(__file__).with_name("v18s_donor.json")).read_text())["manual_exception_lane"]
 ids=sum(len(a["manual_verification_source_identities"]) for a in x)
 post=sum(1 for a in x if a["post_manual_relationship_analysis_required"])
 return {"status":"ok","version":VERSION,
 "mode":"VERIFICATION_EXCEPTION_CONTINUING_RESEARCH_LANE_EXACT_V18R_READ_ONLY",
 "summary":{"manual_verification_properties":len(x),"manual_verification_source_identities":ids,
 "post_manual_relationship_analysis_properties":post,
 "automatic_suffolk_gis_recheck_exhausted_for_all":all(a["automatic_suffolk_gis_recheck_exhausted"] for a in x),
 "research_continues_for_all":all(a["research_may_continue"] for a in x),
 "contact_blocked_pending_required_verification":sum(1 for a in x if a["contact_readiness"]=="BLOCKED_PENDING_REQUIRED_VERIFICATION"),
 "database_writes":0},
 "purpose":"Park the exact V18R unresolved identities in a manual-verification exception lane, prevent repeat GIS cycling, and allow PMI research to continue.",
 "manual_exception_lane":x,
 "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
 "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
