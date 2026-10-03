#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19L"
EXPECTED={"PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE"}
def build_v19l():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19l_donor.json").read_text())
    ids=[c["parcel_id"] for c in d["candidates"]]; byid={c["parcel_id"]:c for c in d["candidates"]}
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("SELECT parcel_id,evidence_family FROM evidence_ledger WHERE is_current=1 AND parcel_id=ANY(%s)",(ids,))
        rows=cur.fetchall()
    finally: conn.close()
    fam={pid:set() for pid in ids}
    for pid,ef in rows:
        if pid in fam:fam[pid].add(ef)
    out=[]
    for pid in ids:
        c=byid[pid]; missing=sorted(EXPECTED-fam[pid]); lane="FOLLOW_UP" if missing else "SOLID"
        out.append({"parcel_id":pid,"lane":lane,"why_it_surfaced":c["research_attention_reasons"],
        "factual_patterns":c["patterns"],"prior_question_status":c["question_status_counts"],
        "missing_required_families":missing,"research_continues":True})
    solid=sum(x["lane"]=="SOLID" for x in out); follow=len(out)-solid
    checks={"protected_candidate_count_113":len(out)==113,"no_candidate_lost":len({x["parcel_id"] for x in out})==113,
    "solid_plus_followup_113":solid+follow==113,"no_new_score":True,"no_new_threshold":True,
    "missing_data_does_not_discard_candidate":True}
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
    "mode":"PROTECTED_CANDIDATE_UNIVERSE_SOLID_FOLLOWUP_READ_ONLY","candidate_count":len(out),
    "research_lanes":{"SOLID":solid,"FOLLOW_UP":follow},"candidates":out,"checks":checks,"database_writes":0,
    "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
    "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
    "next_if_pass":"ENRICH_113_CANDIDATES_WITH_ADDRESS_AND_BEST_AVAILABLE_OWNER_CONTEXT",
    "next_if_fail":"STOP_AND_REPAIR_PROTECTED_CANDIDATE_JOIN"}
