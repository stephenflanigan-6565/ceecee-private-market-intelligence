#!/usr/bin/env python3
"""V18L — Factual case synthesis over exact locked V18K1 113-candidate lane. Read-only."""
import json
from pathlib import Path
VERSION="V18L"
def build_v18l():
    c=json.loads((Path(__file__).with_name("v18l_donor.json")).read_text())["candidates"]
    shapes={}
    categories={}
    for x in c:
        s=x["case_synthesis"]["case_shape"]; shapes[s]=shapes.get(s,0)+1
        k=x["operational_category"]; categories[k]=categories.get(k,0)+1
    return {"status":"ok","version":VERSION,
      "mode":"FACTUAL_CASE_SYNTHESIS_EXACT_113_READ_ONLY",
      "summary":{"candidate_properties":len(c),"case_shape_counts":shapes,
        "operational_category_counts":categories,
        "research_continues_for_all_candidates":all(x["research_may_continue"] for x in c),
        "database_writes":0},
      "purpose":"Connect already-established factual dimensions into an explainable property research case without creating a seller score or motivation inference.",
      "candidates":c,
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}}
