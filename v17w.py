#!/usr/bin/env python3
"""V17W — exact four-identity controlled evidence-memory update."""
import json, os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import psycopg
from v17v import build_v17v

VERSION="V17W"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

def _sid(v):
    if v is None: return None
    try:
        d=Decimal(str(v))
        return str(d.quantize(Decimal(1))) if d==d.to_integral() else format(d.normalize(),"f")
    except (InvalidOperation,ValueError):
        return str(v).strip()

def _iso(v):
    if v is None: return None
    if isinstance(v,(int,float)):
        return datetime.fromtimestamp(v/1000,tz=timezone.utc).isoformat()
    return str(v)

def _fetch(parcel):
    q={"where":f"PARCELID='{parcel}'","outFields":",".join(FIELDS),"returnGeometry":"false","f":"json"}
    req=Request(SERVICE+"?"+urlencode(q),headers={"User-Agent":"PrivateMarketIntelligence/17W factual-memory"})
    with urlopen(req,timeout=30) as r: data=json.loads(r.read().decode())
    if data.get("error"): raise RuntimeError(str(data["error"]))
    return [x.get("attributes") or {} for x in data.get("features") or []]

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def build_v17w():
    plan=build_v17v()
    if plan.get("status")!="ok": raise RuntimeError("V17V prerequisite not ok")
    targets=plan.get("memory_update_plan") or []
    if len(targets)!=4: raise RuntimeError("Expected exactly four authorized identity updates")

    fresh={}
    for t in targets:
        rows=_fetch(t["parcel_id"])
        hit=next((r for r in rows if _sid(r.get("TRANSHISSEQ"))==_sid(t["source_record_id"])),None)
        if not hit: raise RuntimeError("Authoritative identity not found: "+t["source_record_id"])
        fresh[(t["parcel_id"],_sid(t["source_record_id"]))]=hit

    updated=0; already_current=0
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM evidence_ledger")
            before=cur.fetchone()[0]
            if before!=18001: raise RuntimeError(f"Protected evidence count precondition failed: {before}")

            for t in targets:
                parcel=t["parcel_id"]; sid=_sid(t["source_record_id"])
                cur.execute("""SELECT evidence_key,payload_json,first_seen_at FROM evidence_ledger
                               WHERE parcel_id=%s AND evidence_family='TRANSFER_TITLE'
                               AND source_record_id IS NOT NULL""",(parcel,))
                candidates=cur.fetchall()
                match=None
                for row in candidates:
                    if _sid(json.loads(row[1]).get("TRANSHISSEQ") if row[1] else None)==sid or _sid(
                        next((x for x in [None] if False),None))==sid:
                        match=row; break
                if match is None:
                    # source_record_id itself may be decimal-formatted in storage
                    for row in candidates:
                        cur.execute("SELECT source_record_id FROM evidence_ledger WHERE evidence_key=%s",(row[0],))
                        sr=cur.fetchone()[0]
                        if _sid(sr)==sid: match=row; break
                if match is None: raise RuntimeError("Stored identity not found: "+sid)

                key,payload_text,first_seen=match
                payload=json.loads(payload_text)
                src=fresh[(parcel,sid)]
                changed=False
                for fld in ("DOCDATE","LIBERPAGE","RECORDDATE"):
                    nv=_iso(src.get(fld))
                    if payload.get(fld)!=nv:
                        payload[fld]=nv; changed=True
                if changed:
                    cur.execute("""UPDATE evidence_ledger SET payload_json=%s,last_seen_at=%s,is_current=1
                                   WHERE evidence_key=%s""",
                                (json.dumps(payload,sort_keys=True,separators=(",",":")),
                                 datetime.now(timezone.utc).isoformat(),key))
                    updated+=1
                else: already_current+=1

            cur.execute("SELECT COUNT(*) FROM evidence_ledger")
            after=cur.fetchone()[0]
            if after!=before: raise RuntimeError("Evidence row count changed unexpectedly")
        conn.commit()

    return {"status":"ok","version":VERSION,"mode":"EXACT_FOUR_IDENTITY_CONTROLLED_MEMORY_UPDATE",
      "summary":{"authorized_identities":4,"updated":updated,"already_current":already_current,
                 "new_rows_created":0,"evidence_count_before":before,"evidence_count_after":after},
      "idempotence_expectation":"SECOND_RUN_UPDATED_0_ALREADY_CURRENT_4",
      "decision_boundary":{"only_exact_four_existing_identities":True,"open_new_identities_written":False,
                           "investigate_promotion_authorized":False},
      "guards":{"new_candidate_created":False,"seller_intent_inferred":False,"seller_scoring":False,
                "contact_authorized":False,"outreach_touched":False,"clerk_kiosk_scraped":False}}
