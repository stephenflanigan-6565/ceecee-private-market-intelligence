#!/usr/bin/env python3
"""V17W2 — canonical-date post-write verifier. Read-only."""
import json, os
from decimal import Decimal, InvalidOperation
import psycopg

VERSION="V17W2"
TARGETS=[
 ("0905003000100047000","1238279",{"DOCDATE":"2026-08-05","LIBERPAGE":"13352 0294","RECORDDATE":"2026-09-29"}),
 ("0905015000400002000","1238166",{"DOCDATE":"2026-07-23","LIBERPAGE":"13351 0906","RECORDDATE":"2026-09-25"}),
 ("0905015000500023000","1237421",{"LIBERPAGE":"13352 0689","RECORDDATE":"2026-09-30"}),
 ("0905019010200020000","1237715",{"DOCDATE":"2026-05-08","LIBERPAGE":"13351 0760","RECORDDATE":"2026-09-24"}),
]
DATE_FIELDS={"DOCDATE","RECORDDATE","ENTRYDATE"}

def _sid(v):
    if v is None:return None
    try:
        d=Decimal(str(v))
        return str(d.quantize(Decimal(1))) if d==d.to_integral() else format(d.normalize(),"f")
    except (InvalidOperation,ValueError):
        return str(v).strip()

def _canon(field,v):
    if v is None:return None
    s=str(v).strip()
    if field in DATE_FIELDS and len(s)>=10:
        return s[:10]
    return s

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def build_v17w2():
    results=[]
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM evidence_ledger")
        total=cur.fetchone()[0]
        for parcel,sid,expected in TARGETS:
            cur.execute("""SELECT source_record_id,payload_json,is_current FROM evidence_ledger
                           WHERE parcel_id=%s AND evidence_family='TRANSFER_TITLE'
                           AND source_record_id IS NOT NULL""",(parcel,))
            hit=None
            for sr,pj,current in cur.fetchall():
                if _sid(sr)==sid:
                    hit=(sr,pj,current); break
            if hit is None:
                results.append({"parcel_id":parcel,"source_record_id":sid,"verified":False,
                                "reason":"STORED_IDENTITY_NOT_FOUND"})
                continue
            payload=json.loads(hit[1])
            checks={k:(_canon(k,payload.get(k))==_canon(k,v)) for k,v in expected.items()}
            results.append({"parcel_id":parcel,"source_record_id":sid,
                            "verified":all(checks.values()) and bool(hit[2]),
                            "is_current":bool(hit[2]),"field_checks":checks,
                            "expected_canonical":{k:_canon(k,v) for k,v in expected.items()},
                            "stored_canonical":{k:_canon(k,payload.get(k)) for k in expected}})
    passed=sum(1 for x in results if x["verified"])
    ok=(passed==4 and total==18001)
    return {"status":"ok" if ok else "verification_failed","version":VERSION,
      "mode":"V17W_CANONICAL_DATE_POST_WRITE_VERIFICATION_READ_ONLY",
      "summary":{"authorized_identities":4,"verified_current":passed,"database_writes":0,
                 "evidence_total":total,"idempotence_proven":ok},
      "results":results,
      "decision_boundary":{"read_only_verification":True,"repeat_write_performed":False,
                           "canonical_date_comparison":True,"investigate_promotion_authorized":False},
      "guards":{"database_writes":False,"new_candidate_created":False,"seller_intent_inferred":False,
                "seller_scoring":False,"contact_authorized":False,"outreach_touched":False,
                "clerk_kiosk_scraped":False}}
