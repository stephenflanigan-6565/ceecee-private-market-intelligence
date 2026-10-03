#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19H1"
def norm(v):
    s="" if v is None else str(v).strip()
    return s[:-2] if s.endswith(".0") else s
def build_v19h1():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19h1_donor.json").read_text())
    t=d["repair_basis"]["target"]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT evidence_key,source_record_id,event_date,quality_state,source,evidence_type
                       FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1
                         AND evidence_family='TRANSFER_TITLE' AND parcel_id=%s
                       ORDER BY event_date, evidence_key""",
                    (d["dry_run_contract"]["market_code"],t["parcel_id"]))
        rows=cur.fetchall()
    finally: conn.close()
    compact=[{"evidence_key":ek,"source_record_id_raw":sid,"source_record_id_normalized":norm(sid),
              "event_date":str(ed) if ed else None,"quality_state":qs,"source":src,"evidence_type":et}
             for ek,sid,ed,qs,src,et in rows]
    exact=[x for x in compact if x["source_record_id_normalized"]==t["authoritative_transhisseq"]]
    key_mentions=[x for x in compact if t["authoritative_transhisseq"] in str(x["evidence_key"])]
    return {"status":"ok","version":VERSION,
      "mode":"PERSISTED_IDENTITY_REPRESENTATION_REPAIR_READ_ONLY",
      "target":t,"parcel_transfer_rows":len(compact),
      "rows":compact,"direct_source_record_id_matches":len(exact),
      "evidence_key_mentions_of_transhisseq":len(key_mentions),
      "finding":"REPORT_ACTUAL_PERSISTED_REPRESENTATION_ONLY_NO_ASSUMPTION",
      "database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"REPAIR_IDEMPOTENT_PERSISTENCE_GATE_USING_PROVEN_PERSISTED_REPRESENTATION"}
