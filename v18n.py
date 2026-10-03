#!/usr/bin/env python3
"""V18N — Current factual episode classification over exact live V18M lane. Read-only."""
import json
from pathlib import Path
VERSION="V18N"
def build_v18n():
    c=json.loads((Path(__file__).with_name("v18n_donor.json")).read_text())["candidates"]
    lanes={}; cats={}; current=0
    for x in c:
        k=x["episode_classification"]["lane"]; lanes[k]=lanes.get(k,0)+1
        cat=x["operational_category"]; cats[cat]=cats.get(cat,0)+1
        if x["chronology_coherence"]["state"] in ("CONNECTED_CURRENT_FACTUAL_CONTEXT","CURRENT_EVENT_CONTEXT_PRESENT"): current+=1
    return {"status":"ok","version":VERSION,
      "mode":"CURRENT_FACTUAL_EPISODE_CLASSIFICATION_EXACT_V18M_113_READ_ONLY",
      "summary":{"candidate_properties":len(c),"v18m_current_context_properties":current,
        "episode_lane_counts":lanes,"operational_category_counts":cats,
        "research_continues_for_all_candidates":all(x["episode_classification"]["research_may_continue"] for x in c),
        "database_writes":0},
      "purpose":"Separate current factual cases by episode structure so deeper research can be targeted without arbitrary scoring or discarding background/follow-up cases.",
      "candidates":c,
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}}
