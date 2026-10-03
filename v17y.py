#!/usr/bin/env python3
"""V17Y — persist exact four open factual-research watch identities idempotently."""
import json, os
from datetime import datetime, timezone
import psycopg
from v17x import build_v17x

VERSION="V17Y"
TABLE="research_watch"

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def build_v17y():
    source=build_v17x()
    if source.get("status")!="ok": raise RuntimeError("V17X prerequisite not ok")
    records=source.get("watch_records") or []
    if len(records)!=4: raise RuntimeError("Expected exactly four V17X watch identities")

    now=datetime.now(timezone.utc).isoformat()
    inserted=0; already_known=0
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
          watch_key TEXT PRIMARY KEY,
          parcel_id TEXT NOT NULL,
          source_record_id TEXT NOT NULL,
          watch_state TEXT NOT NULL,
          recheck_source TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          is_open INTEGER NOT NULL DEFAULT 1
        )""")
        cur.execute("SELECT COUNT(*) FROM evidence_ledger")
        evidence_before=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='BASELINE'")
        baseline_before=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='INVESTIGATE'")
        investigate_before=cur.fetchone()[0]

        for r in records:
            key=f"{r['parcel_id']}|{r['source_record_id']}|AUTHORITATIVE_RECORDING_METADATA_COMPLETION"
            cur.execute(f"SELECT watch_key FROM {TABLE} WHERE watch_key=%s",(key,))
            if cur.fetchone():
                cur.execute(f"UPDATE {TABLE} SET last_seen_at=%s,is_open=1 WHERE watch_key=%s",(now,key))
                already_known+=1
            else:
                cur.execute(f"""INSERT INTO {TABLE}
                  (watch_key,parcel_id,source_record_id,watch_state,recheck_source,payload_json,
                   first_seen_at,last_seen_at,is_open)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)""",
                  (key,r["parcel_id"],r["source_record_id"],r["watch_state"],r["recheck_source"],
                   json.dumps(r,sort_keys=True,separators=(",",":")),now,now))
                inserted+=1

        cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE is_open=1")
        open_total=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM evidence_ledger"); evidence_after=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='BASELINE'"); baseline_after=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='INVESTIGATE'"); investigate_after=cur.fetchone()[0]
        if (evidence_before,baseline_before,investigate_before)!=(evidence_after,baseline_after,investigate_after):
            raise RuntimeError("Protected state changed unexpectedly")
      conn.commit()

    return {"status":"ok","version":VERSION,"mode":"OPEN_RESEARCH_WATCH_PERSISTENCE",
      "summary":{"authorized_watch_identities":4,"inserted":inserted,"already_known":already_known,
                 "open_watch_rows":open_total},
      "protected_counts_before":{"evidence_total":evidence_before,"baseline":baseline_before,"investigate":investigate_before},
      "protected_counts_after":{"evidence_total":evidence_after,"baseline":baseline_after,"investigate":investigate_after},
      "protected_state_unchanged":True,
      "idempotence_expectation":"SECOND_RUN_INSERTED_0_ALREADY_KNOWN_4",
      "decision_boundary":{"research_watch_only":True,"evidence_ledger_written":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"VERIFY_SECOND_RUN_IDEMPOTENCE_THEN_BUILD_TARGETED_WATCH_RECHECK"},
      "guards":{"new_candidate_created":False,"seller_intent_inferred":False,"seller_scoring":False,
        "contact_authorized":False,"outreach_touched":False,"clerk_kiosk_scraped":False}}
