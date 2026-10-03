#!/usr/bin/env python3
"""V18M — Chronology coherence over exact live V18L 113-candidate lane. Read-only."""
import json
from pathlib import Path
VERSION="V18M"
def build_v18m():
    c=json.loads((Path(__file__).with_name("v18m_donor.json")).read_text())["candidates"]
    states={}; cats={}
    for x in c:
        s=x["chronology_coherence"]["state"]; states[s]=states.get(s,0)+1
        k=x["operational_category"]; cats[k]=cats.get(k,0)+1
    return {"status":"ok","version":VERSION,
      "mode":"CHRONOLOGY_COHERENCE_EXACT_LIVE_V18L_113_READ_ONLY",
      "summary":{"candidate_properties":len(c),"coherence_state_counts":states,
        "operational_category_counts":cats,
        "research_continues_for_all_candidates":all(x["chronology_coherence"]["research_may_continue"] for x in c),
        "database_writes":0},
      "purpose":"Separate connected current factual context from historical background and insufficient chronology without scoring or excluding incomplete properties.",
      "candidates":c,
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}}
