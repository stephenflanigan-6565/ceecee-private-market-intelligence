#!/usr/bin/env python3
"""V18K1 — Exact V18E 113-candidate categorization repair. Read-only."""
import json
from pathlib import Path
VERSION="V18K1"
def build_v18k1():
    c=json.loads((Path(__file__).with_name("v18k1_donor.json")).read_text())["candidates"]
    clean=sum(x["operational_category"]=="CLEAN_RESEARCH_READY" for x in c)
    follow=len(c)-clean
    reasons={}
    qs={}
    for x in c:
        for r in x["research_attention_reasons"]: reasons[r]=reasons.get(r,0)+1
        for k,v in x["v18e_question_status_counts"].items(): qs[k]=qs.get(k,0)+v
    return {"status":"ok","version":VERSION,
      "mode":"EXACT_LOCKED_V18E_CANDIDATE_CATEGORIZATION_READ_ONLY",
      "summary":{"research_attention_candidates":len(c),
        "operational_category_counts":{"CLEAN_RESEARCH_READY":clean,"FOLLOW_UP_REQUIRED":follow},
        "reason_counts":reasons,"question_status_counts":qs,
        "research_continues_for_all_candidates":all(x["research_may_continue"] for x in c),
        "database_writes":0},
      "donor_integrity":{"exact_v18e_candidate_array_used":True,
        "candidate_count_matches_locked_v18e":len(c)==113,
        "questions_match_locked_v18e":sum(qs.values())==184,
        "locked_v18e_expected":{"candidate_properties":113,"questions_evaluated":184,
          "question_status_counts":{"ANSWERED":140,"PARTIAL":40,"UNRESOLVED":4}}},
      "categories":{"CLEAN_RESEARCH_READY":"Continue deeper automated research.",
        "FOLLOW_UP_REQUIRED":"Continue automated research; unresolved verification remains attached for later human completion."},
      "candidates":c,
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}}
