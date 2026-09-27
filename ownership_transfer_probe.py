#!/usr/bin/env python3
"""V15F1 read-only source-isolation diagnostics for Suffolk ownership/current transfer.
No owner names are returned. No database writes are performed.
"""
from datetime import datetime, timezone
import json, urllib.parse, urllib.request, urllib.error
from db import connect, execute, backend

BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
OWNER=BASE+"/TaxParcelOwner/FeatureServer/0/query"
TRANSFER=BASE+"/TaxParcelTransferCurrent/FeatureServer/0/query"
DISTRICT_PREFIX="0905"
PAGE=1000

def utc(): return datetime.now(timezone.utc).isoformat()

def canonical_ids():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id FROM properties WHERE district=? AND active=1",("0905",)).fetchall()
        return {str(r[0]) for r in rows}
    finally:
        c.close()

def fetch(url, params):
    u=url+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(u,headers={"User-Agent":"Private-Market-Intelligence/15F1","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            data=json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"UPSTREAM_HTTP_{e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError("UPSTREAM_URL_ERROR") from e
    if "error" in data:
        err=data.get("error") or {}
        raise RuntimeError(f"ARCGIS_ERROR_{err.get('code','UNKNOWN')}")
    return data

def fetch_all(url, fields):
    out=[]; offset=0; pages=0
    while True:
        data=fetch(url,{
            "where":f"PARCELID LIKE '{DISTRICT_PREFIX}%'",
            "outFields":fields,
            "returnGeometry":"false","resultOffset":offset,
            "resultRecordCount":PAGE,"orderByFields":"PARCELID","f":"json"
        })
        feats=data.get("features",[])
        pages += 1
        out.extend(x.get("attributes",{}) for x in feats)
        if len(feats)<PAGE and not data.get("exceededTransferLimit"):
            break
        if not feats: break
        offset += len(feats)
    return out,pages

def _base(mode):
    return {"status":"ok","mode":mode,"generated_at":utc(),"database_backend":backend(),
            "district":"0905","database_writes":0,"property_data_touched":False,
            "ownership_data_touched":False,"transfer_data_touched":False,
            "seller_scoring_touched":False,"opportunity_data_touched":False,"outreach_touched":False}

def probe_owner_only():
    canonical=canonical_ids()
    owners,pages=fetch_all(OWNER,"PARCELID,FIRSTNAME,LASTNAME,OWNERNAME")
    pids=[str(a.get("PARCELID")) for a in owners if a.get("PARCELID") is not None]
    matched={p for p in pids if p in canonical}
    missing=sorted(canonical-matched)
    r=_base("READ_ONLY_OWNER_SOURCE_DIAGNOSTIC")
    r.update({"canonical_active_parcels":len(canonical),"source":"Suffolk County TaxParcelOwner",
              "source_pages":pages,"records_fetched":len(owners),"parcels_with_owner_record":len(matched),
              "parcels_without_owner_record":len(missing),
              "records_outside_canonical_universe":sum(1 for p in pids if p not in canonical),
              "missing_sample_parcel_ids":missing[:10],"owner_names_exposed_in_response":False})
    return r

def probe_transfer_only():
    canonical=canonical_ids()
    transfers,pages=fetch_all(TRANSFER,"PARCELID,TRANSHISSEQ,RECORDDATE,DOCNUM,DOCCODE,SALEDATE,SALEPRICE")
    pids=[str(a.get("PARCELID")) for a in transfers if a.get("PARCELID") is not None]
    matched={p for p in pids if p in canonical}
    missing=sorted(canonical-matched)
    r=_base("READ_ONLY_CURRENT_TRANSFER_SOURCE_DIAGNOSTIC")
    r.update({"canonical_active_parcels":len(canonical),"source":"Suffolk County TaxParcelTransferCurrent",
              "source_pages":pages,"records_fetched":len(transfers),"parcels_with_current_transfer_record":len(matched),
              "parcels_without_current_transfer_record":len(missing),
              "records_outside_canonical_universe":sum(1 for p in pids if p not in canonical),
              "missing_sample_parcel_ids":missing[:10]})
    return r


def _one_canonical_id():
    c=connect()
    try:
        row=execute(c,"SELECT parcel_id FROM properties WHERE district=? AND active=1 ORDER BY parcel_id LIMIT 1",("0905",)).fetchone()
        if not row:
            raise RuntimeError("NO_CANONICAL_PARCEL")
        return str(row[0])
    finally:
        c.close()

def probe_owner_handshake():
    """Bounded one-parcel upstream handshake; designed to complete well inside web-worker timeout."""
    pid=_one_canonical_id()
    data=fetch(OWNER,{
        "where":f"PARCELID = '{pid}'",
        "outFields":"PARCELID",
        "returnGeometry":"false",
        "resultRecordCount":1,
        "f":"json"
    })
    feats=data.get("features",[])
    r=_base("READ_ONLY_OWNER_SOURCE_HANDSHAKE")
    r.update({"source":"Suffolk County TaxParcelOwner","probe_parcel_id":pid,
              "records_returned":len(feats),"owner_names_requested":False,
              "owner_names_exposed_in_response":False,"bounded_probe":True})
    return r
