#!/usr/bin/env python3
import os,json,re
from pathlib import Path
VERSION="V19H3"
def digits(v): return re.sub(r"\D","",str(v or ""))
def norm(v):
    s="" if v is None else str(v).strip()
    return s[:-2] if s.endswith(".0") else s
def build_v19h3():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19h3_donor.json").read_text())
    canon=d["repair"]["target_parcel"]; tid=d["repair"]["target_identity"]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT evidence_key,parcel_id,market_code,source_record_id,event_date,quality_state,source,evidence_type
                       FROM evidence_ledger
                       WHERE is_current=1 AND evidence_family='TRANSFER_TITLE'""")
        rows=cur.fetchall()
    finally: conn.close()
    matches=[]
    market_counts={}
    for ek,pid,mc,sid,ed,qs,src,et in rows:
        market_counts[str(mc)] = market_counts.get(str(mc),0)+1
        if digits(pid)==canon:
            matches.append({"evidence_key":ek,"parcel_id_raw":pid,"market_code":mc,
              "source_record_id_raw":sid,"source_record_id_normalized":norm(sid),
              "event_date":str(ed) if ed else None,"quality_state":qs,"source":src,"evidence_type":et})
    identity=[x for x in matches if x["source_record_id_normalized"]==tid]
    checks={
      "locked_transfer_count_restored":len(rows)==d["repair"]["locked_expected_transfer_rows"],
      "target_parcel_found":len(matches)>0,
      "target_identity_1239577_found":len(identity)==1
    }
    passed=all(checks.values())
    return {"status":"ok" if passed else "failed","version":VERSION,
      "mode":"MARKET_CODE_FILTER_REMOVAL_IDENTITY_REPAIR_READ_ONLY",
      "transfer_rows_scanned":len(rows),"market_code_counts":market_counts,
      "target_parcel":canon,"target_parcel_transfer_rows":len(matches),
      "target_rows":matches,"target_identity_matches":len(identity),
      "checks":checks,"repair_verified":passed,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"REPAIR_IDEMPOTENT_PERSISTENCE_GATE_WITH_PROVEN_FILTER_AND_IDENTITY",
      "next_if_fail":"STOP_AND_TRACE_LEDGER_FOUNDATION_QUERY_CONTRACT"}
