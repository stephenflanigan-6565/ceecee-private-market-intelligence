#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19I"
def norm(v):
    s="" if v is None else str(v).strip()
    return s[:-2] if s.endswith(".0") else s
def build_v19i():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19i_donor.json").read_text())
    c=d["locked_identity_contract"]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT evidence_key,parcel_id,market_code,evidence_family,evidence_type,
                              source,source_record_id,event_date,quality_state
                       FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1
                         AND evidence_family=%s AND evidence_type=%s
                         AND source=%s AND parcel_id=%s""",
                    (c["market_code"],c["evidence_family"],c["evidence_type"],c["source"],c["parcel_id"]))
        rows=cur.fetchall()
    finally: conn.close()
    matches=[]
    for ek,pid,mc,ef,et,src,sid,ed,qs in rows:
        if norm(sid)==c["source_record_id_normalized"]:
            matches.append({"evidence_key":ek,"parcel_id":pid,"market_code":mc,"evidence_family":ef,
              "evidence_type":et,"source":src,"source_record_id_raw":sid,
              "source_record_id_normalized":norm(sid),"event_date":str(ed) if ed else None,"quality_state":qs})
    disposition="NO_OP_ALREADY_REMEMBERED" if len(matches)==1 else ("INSERT_CANDIDATE_ONLY" if len(matches)==0 else "STOP_DUPLICATE_IDENTITY_CONFLICT")
    checks={
      "correct_market_code":c["market_code"]=="WESTHAMPTON_BEACH_NY",
      "target_parcel_has_five_transfer_rows":len(rows)==5,
      "exactly_one_normalized_identity_match":len(matches)==1,
      "idempotent_noop_selected":disposition=="NO_OP_ALREADY_REMEMBERED",
      "dry_run_only":True,"no_investigate_promotion":True,"no_contact_authorization":True
    }
    passed=all(checks.values())
    return {"status":"ok" if passed else "failed","version":VERSION,
      "mode":"REPAIRED_IDEMPOTENT_FACTUAL_MEMORY_GATE_READ_ONLY",
      "target":c,"parcel_transfer_rows":len(rows),"existing_identity_matches":matches,
      "existing_identity_match_count":len(matches),"persistence_disposition":disposition,
      "checks":checks,"idempotency_gate_passed":passed,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"VALIDATE_ABSENT_IDENTITY_INSERT_PLAN_IN_MEMORY_ONLY",
      "next_if_fail":"STOP_AND_REPAIR_IDEMPOTENCY_GATE"}
