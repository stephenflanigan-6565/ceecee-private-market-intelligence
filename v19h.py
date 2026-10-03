#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19H"
def norm(v):
    s="" if v is None else str(v).strip()
    return s[:-2] if s.endswith(".0") else s
def build_v19h():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19h_donor.json").read_text())
    o=d["real_authoritative_observation"]; target=norm(o["source_record_id"])
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT evidence_key,parcel_id,source_record_id,event_date,quality_state,source
                       FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1
                         AND evidence_family='TRANSFER_TITLE'
                         AND parcel_id=%s""",(d["dry_run_contract"]["market_code"],o["parcel_id"]))
        rows=cur.fetchall()
    finally: conn.close()
    matches=[]
    for ek,pid,sid,ed,qs,source in rows:
        if norm(sid)==target:
            matches.append({"evidence_key":ek,"parcel_id":pid,"source_record_id":norm(sid),
                            "event_date":str(ed) if ed else None,"quality_state":qs,"source":source})
    if len(matches)==1:
        disposition="NO_OP_ALREADY_REMEMBERED"
    elif len(matches)==0:
        disposition="INSERT_CANDIDATE_ONLY"
    else:
        disposition="STOP_DUPLICATE_IDENTITY_CONFLICT"
    checks={
      "identity_rule_is_transhisseq":target=="1239577",
      "duplicate_identity_count_safe":len(matches)<=1,
      "dry_run_only":True,
      "expected_noop_for_proven_observation":disposition=="NO_OP_ALREADY_REMEMBERED",
      "no_investigate_promotion":True,"no_contact_authorization":True
    }
    passed=all(checks.values())
    return {"status":"ok" if passed else "failed","version":VERSION,
      "mode":"IDEMPOTENT_FACTUAL_MEMORY_PERSISTENCE_DRY_RUN",
      "target":{"parcel_id":o["parcel_id"],"source_record_id":target,"evidence_family":"TRANSFER_TITLE"},
      "existing_identity_matches":matches,"existing_identity_match_count":len(matches),
      "persistence_disposition":disposition,"checks":checks,"dry_run_passed":passed,
      "database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"LOCK_IDEMPOTENT_PERSISTENCE_GATE_AND_VALIDATE_ABSENT_IDENTITY_INSERT_PLAN_IN_MEMORY_ONLY",
      "next_if_fail":"STOP_AND_REPAIR_PERSISTENCE_IDENTITY_GATE"}
