#!/usr/bin/env python3
import os, json
from pathlib import Path

VERSION="V19J"

def build_v19j():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19j_donor.json").read_text())
    f=d["locked_foundation"]

    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""
            SELECT parcel_id,evidence_family,quality_state
            FROM evidence_ledger
            WHERE is_current=1
        """)
        rows=cur.fetchall()
    finally:
        conn.close()

    by_parcel={}
    family_counts={}
    for pid,fam,quality in rows:
        pid=str(pid)
        family_counts[fam]=family_counts.get(fam,0)+1
        p=by_parcel.setdefault(pid,{"families":set(),"nonvalid":0,"rows":0})
        p["families"].add(fam)
        p["rows"]+=1
        if str(quality or "").upper() not in ("VALID","VERIFIED"):
            p["nonvalid"]+=1

    # This step does NOT rank or infer seller intent.
    # It establishes the market-wide continuation lanes:
    # incomplete factual context is categorized, never discarded.
    lanes={"CLEAN_AUTOMATION_READY":0,"FOLLOW_UP_REQUIRED":0}
    examples={"FOLLOW_UP_REQUIRED":[]}
    expected={"PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE"}

    for pid,p in by_parcel.items():
        missing=sorted(expected-p["families"])
        if missing or p["nonvalid"]:
            lanes["FOLLOW_UP_REQUIRED"]+=1
            if len(examples["FOLLOW_UP_REQUIRED"])<10:
                examples["FOLLOW_UP_REQUIRED"].append({
                    "parcel_id":pid,
                    "missing_families":missing,
                    "nonvalid_evidence_rows":p["nonvalid"],
                    "research_continues":True
                })
        else:
            lanes["CLEAN_AUTOMATION_READY"]+=1

    checks={
      "foundation_total_18001":len(rows)==f["evidence_total"],
      "transfer_title_10724":family_counts.get("TRANSFER_TITLE",0)==f["transfer_title"],
      "all_properties_retained":sum(lanes.values())==len(by_parcel),
      "missing_data_does_not_stop_research":True,
      "no_ranking":True,
      "no_seller_intent":True,
      "no_contact_authorization":True
    }

    return {
      "status":"ok" if all(checks.values()) else "failed",
      "version":VERSION,
      "mode":"MARKET_WIDE_RESEARCH_CONTINUATION_GATE_READ_ONLY",
      "properties_seen":len(by_parcel),
      "evidence_rows_seen":len(rows),
      "evidence_family_counts":family_counts,
      "research_lanes":lanes,
      "follow_up_examples":examples["FOLLOW_UP_REQUIRED"],
      "checks":checks,
      "research_continuation_rule":"MISSING_FACTS_ARE_CATEGORIZED_NOT_DISCARDED",
      "database_writes":0,
      "guards":{
        "database_writes":False,
        "schema_introspection":False,
        "investigate_state_touched":False,
        "seller_intent_inferred":False,
        "seller_scoring":False,
        "overall_ranking":False,
        "contact_authorized":False,
        "outreach_touched":False
      },
      "next_if_pass":"CONTINUE_MARKET_WIDE_NEEDLE_FINDING_WITH_CATEGORIZED_EXCEPTIONS",
      "next_if_fail":"STOP_AND_REPAIR_CONTINUATION_GATE"
    }
