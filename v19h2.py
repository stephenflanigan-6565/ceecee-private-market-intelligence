#!/usr/bin/env python3
import os,json,re
from pathlib import Path
VERSION="V19H2"
def digits(v): return re.sub(r"\D","",str(v or ""))
def build_v19h2():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19h2_donor.json").read_text())
    canon=d["parcel_identity_repair"]["target_canonical"]; suffix=canon[-12:]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        # Known schema only. Broad transfer-family read is bounded to parcel_id + dates/ids, not payloads.
        cur.execute("""SELECT parcel_id,source_record_id,event_date,quality_state,evidence_key
                       FROM evidence_ledger WHERE market_code=%s AND is_current=1
                       AND evidence_family='TRANSFER_TITLE'""",(d["dry_run_contract"]["market_code"],))
        rows=cur.fetchall()
    finally: conn.close()
    # Exact normalized match first; suffix is reported separately only as diagnostic evidence, never auto-accepted.
    exact=[]; suffix_hits=[]
    for pid,sid,ed,qs,ek in rows:
        item={"parcel_id_raw":pid,"parcel_id_digits":digits(pid),"source_record_id":sid,
              "event_date":str(ed) if ed else None,"quality_state":qs,"evidence_key":ek}
        if digits(pid)==canon: exact.append(item)
        elif digits(pid).endswith(suffix): suffix_hits.append(item)
    reps=sorted(set(x["parcel_id_raw"] for x in exact))
    disposition="CANONICAL_NORMALIZED_REPRESENTATION_FOUND" if reps else ("SUFFIX_CANDIDATE_REQUIRES_VALIDATION" if suffix_hits else "NO_LEDGER_PARCEL_REPRESENTATION_FOUND")
    return {"status":"ok","version":VERSION,"mode":"LEDGER_PARCEL_IDENTITY_REPRESENTATION_READ_ONLY",
      "target_canonical":canon,"transfer_rows_scanned":len(rows),"exact_normalized_match_count":len(exact),
      "exact_raw_representations":reps,"exact_matches":exact,
      "suffix_candidate_count":len(suffix_hits),"suffix_candidates":suffix_hits[:20],
      "disposition":disposition,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"REPAIR_PERSISTENCE_GATE_WITH_PROVEN_LEDGER_PARCEL_REPRESENTATION"}
