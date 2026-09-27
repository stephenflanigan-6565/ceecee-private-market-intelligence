#!/usr/bin/env python3
"""Westhampton Beach canonical parcel-universe collector.

V15B1 repairs canonical comparison in the V15B parcel feed. It normalizes
source values to the PostgreSQL schema before comparing or writing them.
It is deliberately narrow: parcels + source snapshots only.
No scoring, opportunities, relationship data, paid data, or outreach.
"""
import hashlib, json, urllib.parse, urllib.request
from datetime import datetime, timezone
from db import connect, execute, backend, insert_id

PARCEL_URL = "https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"
SOURCE_NAME = "Suffolk County TaxParcelPolygon"
WESTHAMPTON_DISTRICT = "0905"
WHERE = "DISTRICT = '0905' AND STATUS = 'A'"
FIELDS = "OBJECTID,PARCELID,DISTRICT,SECTION,BLOCK,LOT,MUNICIPALITY,ZIPCODE,FULLADDRESS,ACREAGE,FRONTAGE,DEPTH,LANDUSE,TITLEFLAG,STATUS,ACREDEED,CREATEDATE,LASTUPDATE"
PAGE_SIZE = 2000


def utc(): return datetime.now(timezone.utc).isoformat()

def _fetch(params):
    url = PARCEL_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent":"Private-Market-Intelligence/15B1"})
    with urllib.request.urlopen(req, timeout=90) as response: payload=json.load(response)
    if "error" in payload: raise RuntimeError(payload["error"])
    return payload

def _pages():
    offset=0
    while True:
        payload=_fetch({"where":WHERE,"outFields":FIELDS,"returnGeometry":"false",
                        "resultOffset":offset,"resultRecordCount":PAGE_SIZE,
                        "orderByFields":"OBJECTID","f":"json"})
        features=payload.get("features",[])
        for feature in features: yield feature.get("attributes",{})
        if len(features)<PAGE_SIZE: break
        offset += len(features)

def _validate(rows):
    ids=[]
    for r in rows:
        pid=str(r.get("PARCELID") or "").strip()
        if not pid: raise ValueError("missing PARCELID")
        if str(r.get("DISTRICT") or "").strip()!=WESTHAMPTON_DISTRICT: raise ValueError("wrong district")
        if str(r.get("STATUS") or "").strip()!="A": raise ValueError("wrong status")
        ids.append(pid)
    if not rows: raise ValueError("empty source universe")
    if len(ids)!=len(set(ids)): raise ValueError("duplicate PARCELID")
    return len(ids)

def probe():
    rows=list(_pages()); unique=_validate(rows)
    return {"status":"ok","mode":"READ_ONLY_PROBE","source":SOURCE_NAME,
            "source_url":PARCEL_URL.rsplit("/query",1)[0],"where":WHERE,"generated_at":utc(),
            "records_fetched":len(rows),"unique_parcel_ids":unique,"database_writes":0,
            "property_data_touched":False,"outreach_touched":False,
            "samples":[{"parcel_id":r.get("PARCELID"),"district":r.get("DISTRICT"),
                        "municipality":r.get("MUNICIPALITY"),"address":r.get("FULLADDRESS"),
                        "status":r.get("STATUS")} for r in rows[:5]]}

def _canonical_payload(r):
    keys=["PARCELID","DISTRICT","SECTION","BLOCK","LOT","MUNICIPALITY","ZIPCODE","FULLADDRESS",
          "ACREAGE","FRONTAGE","DEPTH","LANDUSE","TITLEFLAG","STATUS","ACREDEED","CREATEDATE","LASTUPDATE"]
    return {k:r.get(k) for k in keys}

def _hash_payload(payload):
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _text(v):
    """Normalize a source value to the TEXT representation stored by the schema."""
    if v is None:
        return None
    s=str(v).strip()
    return s or None

def _number(v):
    """Normalize a source value to the DOUBLE PRECISION representation."""
    if v is None or v == "":
        return None
    return float(v)

def _storage_vals(r):
    """Return values in exact properties-table storage types/order.

    ArcGIS can emit numeric-looking section/block/lot/date values as numbers.
    PostgreSQL returns those columns as TEXT after storage. Comparing raw source
    JSON to database rows therefore creates false updates. Normalize first.
    """
    return (
        _text(r.get("DISTRICT")), _text(r.get("SECTION")), _text(r.get("BLOCK")),
        _text(r.get("LOT")), _text(r.get("MUNICIPALITY")), _text(r.get("ZIPCODE")),
        _text(r.get("FULLADDRESS")), _number(r.get("ACREAGE")), _text(r.get("FRONTAGE")),
        _text(r.get("DEPTH")), _text(r.get("LANDUSE")), _text(r.get("TITLEFLAG")),
        _text(r.get("STATUS")), _number(r.get("ACREDEED")), _text(r.get("CREATEDATE")),
        _text(r.get("LASTUPDATE"))
    )

def populate():
    """Idempotently write the verified universe into canonical property memory."""
    rows=list(_pages()); _validate(rows)
    now=utc(); c=connect(); run_id=None
    inserted=updated=unchanged=snapshots_added=0
    try:
        run_id=insert_id(c,"INSERT INTO source_runs(source,started_at,status) VALUES(?,?,?)",
                         (SOURCE_NAME,now,"RUNNING"))
        for r in rows:
            pid=str(r.get("PARCELID")).strip()
            cur=execute(c,"SELECT district,section,block,lot,municipality,zipcode,full_address,acreage,frontage,depth,land_use,title_flag,status,deed_acreage,source_created_at,source_last_update FROM properties WHERE parcel_id=?",(pid,))
            old=cur.fetchone()
            vals=_storage_vals(r)
            if old is None:
                execute(c,"""INSERT INTO properties(parcel_id,district,section,block,lot,municipality,zipcode,full_address,acreage,frontage,depth,land_use,title_flag,status,deed_acreage,source_created_at,source_last_update,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(pid,*vals,now,now))
                inserted += 1
            else:
                oldvals=tuple(old)
                if oldvals != vals:
                    execute(c,"""UPDATE properties SET district=?,section=?,block=?,lot=?,municipality=?,zipcode=?,full_address=?,acreage=?,frontage=?,depth=?,land_use=?,title_flag=?,status=?,deed_acreage=?,source_created_at=?,source_last_update=?,last_seen_at=? WHERE parcel_id=?""",(*vals,now,pid))
                    updated += 1
                else:
                    execute(c,"UPDATE properties SET last_seen_at=? WHERE parcel_id=?",(now,pid)); unchanged += 1
            payload,payload_hash=_hash_payload(_canonical_payload(r))
            before=getattr(c,"total_changes",None)
            if backend()=="postgres":
                cur=execute(c,"INSERT INTO snapshots(parcel_id,source,observed_at,payload_json,payload_hash) VALUES(?,?,?,?,?) ON CONFLICT(parcel_id,source,payload_hash) DO NOTHING",(pid,SOURCE_NAME,now,payload,payload_hash))
                if cur.rowcount==1: snapshots_added += 1
            else:
                cur=execute(c,"INSERT OR IGNORE INTO snapshots(parcel_id,source,observed_at,payload_json,payload_hash) VALUES(?,?,?,?,?)",(pid,SOURCE_NAME,now,payload,payload_hash))
                if getattr(cur,"rowcount",0)==1: snapshots_added += 1
        execute(c,"UPDATE source_runs SET completed_at=?,records_seen=?,changed_records=?,status=? WHERE id=?",
                (utc(),len(rows),inserted+updated,"SUCCESS",run_id))
        c.commit()
        total=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(WESTHAMPTON_DISTRICT,)).fetchone()[0]
        return {"status":"ok","mode":"CANONICAL_UNIVERSE_POPULATION","database_backend":backend(),
                "source":SOURCE_NAME,"where":WHERE,"records_fetched":len(rows),"inserted":inserted,
                "updated":updated,"unchanged":unchanged,"snapshots_added":snapshots_added,
                "canonical_active_parcels":total,"source_run_id":run_id,
                "property_data_touched":True,"opportunity_data_touched":False,"outreach_touched":False,
                "generated_at":utc()}
    except Exception as e:
        c.rollback()
        try:
            if run_id is not None:
                execute(c,"UPDATE source_runs SET completed_at=?,status=?,error=? WHERE id=?",(utc(),"FAILED",type(e).__name__,run_id)); c.commit()
        except Exception: pass
        raise
    finally: c.close()
