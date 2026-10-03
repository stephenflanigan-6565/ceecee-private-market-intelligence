#!/usr/bin/env python3
import json, os
from pathlib import Path
VERSION="V19A"

def _connect():
    import psycopg2
    url=os.environ.get("DATABASE_URL")
    if not url: raise RuntimeError("DATABASE_URL not configured")
    return psycopg2.connect(url)

def build_v19a():
    d=json.loads((Path(__file__).with_name("v19a_donor.json")).read_text())
    exp=d["locked_expected"]; market=d["market_code"]
    conn=_connect()
    try:
        cur=conn.cursor()
        # Proven V16A evidence_ledger columns only. Read-only aggregate queries.
        cur.execute("""
          SELECT evidence_family, COUNT(*), COUNT(DISTINCT parcel_id)
          FROM evidence_ledger
          WHERE market_code=%s AND is_current=1
          GROUP BY evidence_family
          ORDER BY evidence_family
        """,(market,))
        rows=cur.fetchall()
        cur.execute("""
          SELECT COUNT(*), COUNT(DISTINCT parcel_id)
          FROM evidence_ledger
          WHERE market_code=%s AND is_current=1
        """,(market,))
        total_rows, distinct_parcels=cur.fetchone()
    finally:
        conn.close()

    fam={r[0]:{"rows":int(r[1]),"distinct_parcels":int(r[2])} for r in rows}
    actual={
      "PROPERTY_CONTEXT":fam.get("PROPERTY_CONTEXT",{}).get("rows",0),
      "ASSESSMENT_CONTEXT":fam.get("ASSESSMENT_CONTEXT",{}).get("rows",0),
      "OWNERSHIP":fam.get("OWNERSHIP",{}).get("rows",0),
      "TRANSFER_TITLE":fam.get("TRANSFER_TITLE",{}).get("rows",0),
      "TOTAL":int(total_rows),
      "RESIDENTIAL_PARCELS":int(distinct_parcels)
    }
    checks={k:{"expected":int(exp[k]),"actual":int(actual[k]),"match":int(exp[k])==int(actual[k])} for k in exp}
    passed=all(x["match"] for x in checks.values())
    return {
      "status":"ok","version":VERSION,
      "mode":"PERSISTENT_FOUNDATION_INVARIANT_VERIFIER_READ_ONLY",
      "market_code":market,
      "foundation_verified":passed,
      "advance_authorized":passed,
      "checks":checks,
      "family_detail":fam,
      "next_if_pass":"BUILD_FULL_2082_MARKET_INTELLIGENCE_FROM_VERIFIED_PERSISTENT_MEMORY",
      "next_if_fail":"STOP_AND_RECONCILE_FOUNDATION_BEFORE_NEW_INTELLIGENCE",
      "database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"external_calls":False,
        "investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,
        "overall_ranking":False,"contact_authorized":False,"outreach_touched":False}
    }
