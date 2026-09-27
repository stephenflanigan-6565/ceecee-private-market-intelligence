#!/usr/bin/env python3
"""V15E Westhampton factual cohort persistence.

Persists the already-verified V15D factual property-use cohort as a separate,
reversible derived layer. Raw official LANDUSE remains untouched on properties.
No seller scoring, opportunities, ownership, or outreach are modified.
"""
from datetime import datetime, timezone
from db import connect, execute, backend

DISTRICT = "0905"
METHOD_VERSION = "V15D_ORPTS_BROAD_COHORT_V1"
RESIDENTIAL_VACANT_CODES = {"310", "311", "312", "314", "315", "320", "321", "322", "323"}
COMMERCIAL_VACANT_CODES = {"330", "331"}
INDUSTRIAL_VACANT_CODES = {"340", "341"}
PUBLIC_UTILITY_VACANT_CODES = {"380"}
COHORT_ORDER = ["RESIDENTIAL_IMPROVED", "RESIDENTIAL_VACANT_LAND", "COMMERCIAL_MIXED",
                "COMMUNITY_PUBLIC_UTILITY", "OTHER_NON_TARGET", "UNRESOLVED"]

def utc(): return datetime.now(timezone.utc).isoformat()

def classify_land_use(code):
    if code is None or str(code).strip() == "": return "UNRESOLVED"
    code = str(code).strip()
    if code.startswith("2"): return "RESIDENTIAL_IMPROVED"
    if code in RESIDENTIAL_VACANT_CODES: return "RESIDENTIAL_VACANT_LAND"
    if code in COMMERCIAL_VACANT_CODES or code.startswith("4"): return "COMMERCIAL_MIXED"
    if code in PUBLIC_UTILITY_VACANT_CODES or code.startswith("6") or code.startswith("8"): return "COMMUNITY_PUBLIC_UTILITY"
    if code in INDUSTRIAL_VACANT_CODES or code.startswith("5") or code.startswith("7") or code.startswith("9"): return "OTHER_NON_TARGET"
    return "UNRESOLVED"

def _ensure_table(c):
    execute(c, """CREATE TABLE IF NOT EXISTS property_classifications(
        parcel_id TEXT PRIMARY KEY,
        raw_land_use TEXT,
        cohort TEXT NOT NULL,
        method_version TEXT NOT NULL,
        first_classified_at TEXT NOT NULL,
        last_verified_at TEXT NOT NULL
    )""")

def preview():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id, full_address, land_use, acreage FROM properties WHERE district=? AND status='A' ORDER BY parcel_id",(DISTRICT,)).fetchall()
        counts={}; by_code={}; samples={}
        for row in rows:
            pid,address,land_use,acreage=tuple(row); cohort=classify_land_use(land_use)
            counts[cohort]=counts.get(cohort,0)+1
            raw=str(land_use).strip() if land_use is not None and str(land_use).strip() else "(missing)"
            by_code[(cohort,raw)]=by_code.get((cohort,raw),0)+1
            if len(samples.setdefault(cohort,[]))<5: samples[cohort].append({"parcel_id":pid,"address":address,"land_use":land_use,"acreage":acreage})
        return {"status":"ok","mode":"READ_ONLY_CLASSIFICATION_PREVIEW","database_backend":backend(),"district":DISTRICT,
                "canonical_active_parcels":len(rows),"classification_applied":False,
                "cohort_counts":[{"cohort":k,"count":counts.get(k,0)} for k in COHORT_ORDER],"cohort_total":sum(counts.values()),
                "code_breakdown":[{"cohort":cohort,"land_use":code,"count":count} for (cohort,code),count in sorted(by_code.items(),key=lambda x:(x[0][0],-x[1],x[0][1]))],
                "samples":samples,"database_writes":0,"property_data_touched":False,"opportunity_data_touched":False,"outreach_touched":False,"generated_at":utc()}
    finally: c.close()

def persist():
    c=connect(); now=utc()
    try:
        _ensure_table(c)
        rows=execute(c,"SELECT parcel_id, land_use FROM properties WHERE district=? AND status='A' ORDER BY parcel_id",(DISTRICT,)).fetchall()
        inserted=updated=unchanged=0; counts={}
        for row in rows:
            pid,land_use=tuple(row); raw=None if land_use is None or str(land_use).strip()=="" else str(land_use).strip(); cohort=classify_land_use(raw)
            counts[cohort]=counts.get(cohort,0)+1
            old=execute(c,"SELECT raw_land_use, cohort, method_version FROM property_classifications WHERE parcel_id=?",(pid,)).fetchone()
            if old is None:
                execute(c,"INSERT INTO property_classifications(parcel_id,raw_land_use,cohort,method_version,first_classified_at,last_verified_at) VALUES(?,?,?,?,?,?)",
                        (pid,raw,cohort,METHOD_VERSION,now,now)); inserted+=1
            else:
                old_raw,old_cohort,old_method=tuple(old)
                if old_raw==raw and old_cohort==cohort and old_method==METHOD_VERSION:
                    unchanged+=1
                else:
                    execute(c,"UPDATE property_classifications SET raw_land_use=?, cohort=?, method_version=?, last_verified_at=? WHERE parcel_id=?",
                            (raw,cohort,METHOD_VERSION,now,pid)); updated+=1
        c.commit()
        total=execute(c,"SELECT COUNT(*) FROM property_classifications pc JOIN properties p ON p.parcel_id=pc.parcel_id WHERE p.district=? AND p.status='A'",(DISTRICT,)).fetchone()[0]
        return {"status":"ok","mode":"FACTUAL_COHORT_PERSISTENCE","database_backend":backend(),"district":DISTRICT,
                "canonical_active_parcels":len(rows),"persisted_active_classifications":total,"method_version":METHOD_VERSION,
                "inserted":inserted,"updated":updated,"unchanged":unchanged,
                "cohort_counts":[{"cohort":k,"count":counts.get(k,0)} for k in COHORT_ORDER],
                "raw_land_use_preserved":True,"seller_scoring_touched":False,"opportunity_data_touched":False,"outreach_touched":False,"generated_at":now}
    except Exception:
        c.rollback(); raise
    finally: c.close()
