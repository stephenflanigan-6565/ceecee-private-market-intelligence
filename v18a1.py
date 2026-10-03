#!/usr/bin/env python3
"""V18A1 — profile integrity repair: transfer DOCCODE extraction + incomplete-profile identification.
Read-only.
"""
import json, os
from collections import Counter, defaultdict
import psycopg

VERSION="V18A1"
FAMILIES=("PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE")

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _payload(v):
    try: return json.loads(v) if v else {}
    except Exception:return {}

def _first(p,*keys):
    for k in keys:
        if p.get(k) not in (None,""): return p.get(k)
    return None

def build_v18a1():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,evidence_type,source_record_id,event_date,payload_json
                       FROM evidence_ledger WHERE is_current=1 ORDER BY parcel_id""")
        rows=cur.fetchall()
    by=defaultdict(list)
    for r in rows: by[r[0]].append(r)

    incomplete=[]; code_profiles=0; code_rows=0; samples=[]
    for parcel,evs in by.items():
        fam=Counter(r[1] for r in evs)
        missing=[f for f in FAMILIES if fam[f]==0]
        if missing:
            incomplete.append({"parcel_id":parcel,"families_missing":missing,
                               "family_counts":{f:fam[f] for f in FAMILIES}})
        codes=Counter()
        transfer_count=0
        for r in evs:
            if r[1]!="TRANSFER_TITLE": continue
            transfer_count+=1
            p=_payload(r[5])
            # Preserve compatibility with historical payload casing/shapes.
            code=_first(p,"DOCCODE","doccode","doc_code","document_code")
            if code:
                codes[str(code)]+=1; code_rows+=1
        if codes:
            code_profiles+=1
            if len(samples)<12:
                samples.append({"parcel_id":parcel,"transfer_title_rows":transfer_count,
                                "transfer_document_codes":dict(sorted(codes.items()))})

    return {"status":"ok","version":VERSION,
      "mode":"PROPERTY_PROFILE_INTEGRITY_REPAIR_READ_ONLY",
      "summary":{"profiles_checked":len(by),"evidence_rows_checked":len(rows),
                 "profiles_with_transfer_document_codes":code_profiles,
                 "transfer_rows_with_document_code":code_rows,
                 "incomplete_profiles":len(incomplete)},
      "incomplete_profile_details":incomplete,
      "document_code_samples":samples,
      "decision_boundary":{"read_only":True,"database_writes":False,
        "profile_integrity_check_only":True,
        "next_step_if_clean":"BUILD_V18B_CROSS_PROPERTY_FACTUAL_COMPARISON_DIMENSIONS"},
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"new_candidate_created":False,
        "contact_authorized":False,"outreach_touched":False}}
