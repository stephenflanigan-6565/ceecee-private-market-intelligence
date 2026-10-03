#!/usr/bin/env python3
"""V17Z — targeted recheck of persisted open research watches. Read-only."""
import json, os
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import psycopg

VERSION="V17Z"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _sid(v):
    if v is None:return None
    try:
        d=Decimal(str(v))
        return str(d.quantize(Decimal(1))) if d==d.to_integral() else format(d.normalize(),"f")
    except (InvalidOperation,ValueError):
        return str(v).strip()

def _date(v):
    if v is None:return None
    if isinstance(v,(int,float)):
        return datetime.fromtimestamp(v/1000,tz=timezone.utc).date().isoformat()
    return str(v)[:10]

def _fetch(parcel):
    q={"where":f"PARCELID='{parcel}'","outFields":",".join(FIELDS),
       "returnGeometry":"false","resultRecordCount":"2000","f":"json"}
    req=Request(SERVICE+"?"+urlencode(q),headers={"User-Agent":"PrivateMarketIntelligence/17Z watch-recheck"})
    with urlopen(req,timeout=30) as r: data=json.loads(r.read().decode())
    if data.get("error"): raise RuntimeError(str(data["error"]))
    return [x.get("attributes") or {} for x in data.get("features") or []]

def build_v17z():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,source_record_id,payload_json
                       FROM research_watch WHERE is_open=1
                       ORDER BY parcel_id,source_record_id""")
        watches=cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM evidence_ledger"); evidence=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='BASELINE'"); baseline=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='INVESTIGATE'"); investigate=cur.fetchone()[0]

    results=[]; errors=[]
    for parcel,sid,payload in watches:
        try:
            rows=_fetch(parcel)
            hit=next((r for r in rows if _sid(r.get("TRANSHISSEQ"))==_sid(sid)),None)
            if hit is None:
                results.append({"parcel_id":parcel,"source_record_id":sid,"identity_found":False,
                                "completion_detected":False})
                continue
            rec={k:(_date(hit.get(k)) if k in ("RECORDDATE","DOCDATE","ENTRYDATE") else hit.get(k)) for k in FIELDS}
            complete=bool(rec.get("RECORDDATE") and rec.get("LIBERPAGE"))
            results.append({"parcel_id":parcel,"source_record_id":sid,"identity_found":True,
                            "completion_detected":complete,
                            "recorddate":rec.get("RECORDDATE"),"liberpage":rec.get("LIBERPAGE"),
                            "doccode":rec.get("DOCCODE"),"docdate":rec.get("DOCDATE"),
                            "entrydate":rec.get("ENTRYDATE"),
                            "next_action":"REEVALUATE_SEQUENCE_AND_PREPARE_CONTROLLED_MEMORY_UPDATE" if complete
                                          else "KEEP_WATCH_OPEN"})
        except Exception as e:
            errors.append({"parcel_id":parcel,"source_record_id":sid,
                           "error_type":type(e).__name__,"error":str(e)[:500]})

    completed=sum(1 for x in results if x.get("completion_detected"))
    return {"status":"ok" if not errors else "partial","version":VERSION,
      "mode":"PERSISTED_OPEN_RESEARCH_WATCH_TARGETED_GIS_RECHECK_READ_ONLY",
      "summary":{"open_watch_rows_read":len(watches),"gis_identities_checked":len(results),
                 "metadata_completions_detected":completed,
                 "still_incomplete":sum(1 for x in results if x.get("identity_found") and not x.get("completion_detected")),
                 "query_errors":len(errors)},
      "results":results,"query_errors":errors,
      "protected_counts":{"evidence_total":evidence,"baseline":baseline,"investigate":investigate},
      "decision_boundary":{"read_only":True,"watch_rows_updated":False,"evidence_ledger_written":False,
        "investigate_promotion_authorized":False,
        "next_step_if_completion_detected":"REEVALUATE_ONLY_COMPLETED_WATCH_IDENTITIES",
        "next_step_if_none":"KEEP_WATCHES_OPEN_AND_RETURN_TO_BROADER_MACHINE_DEVELOPMENT"},
      "guards":{"database_writes":False,"new_candidate_created":False,"seller_intent_inferred":False,
        "seller_scoring":False,"contact_authorized":False,"outreach_touched":False,"clerk_kiosk_scraped":False}}
