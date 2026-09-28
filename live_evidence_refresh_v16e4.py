#!/usr/bin/env python3
"""V16E4 — write-enabled Suffolk live source refresh.
Uses the V16E3-proven bounded query shape. Writes only new raw source observations.
"""
import json, urllib.parse, urllib.request, time
from datetime import datetime, timezone
from db import connect, execute

VERSION="V16E4"
MODE="SUFFOLK_LIVE_EVIDENCE_REFRESH"
MARKET="WESTHAMPTON_BEACH_NY"
BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; PrivateMarketIntelligence/16E4)",
         "Accept":"application/json,text/plain,*/*"}
SOURCES={
 "owner":(f"{BASE}/TaxParcelOwner/FeatureServer/0/query",
          "OBJECTID,PARCELID,FIRSTNAME,LASTNAME,OWNERNAME"),
 "transfer":(f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query",
          "OBJECTID,PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ"),
}

def _call(url,params):
    target=url+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(target,headers=HEADERS,method="GET")
    with urllib.request.urlopen(req,timeout=30) as r:
        data=json.loads(r.read().decode("utf-8","replace"))
    if data.get("error"): raise RuntimeError(str(data["error"]))
    return data

def _fetch_all(url,fields):
    where="PARCELID LIKE '0905%'"
    count=int(_call(url,{"where":where,"returnCountOnly":"true","f":"json"}).get("count") or 0)
    rows=[]; offset=0; page=1000
    while offset<count:
        d=_call(url,{"where":where,"outFields":fields,"returnGeometry":"false",
                     "orderByFields":"OBJECTID","resultOffset":offset,
                     "resultRecordCount":page,"f":"json"})
        batch=[f.get("attributes") or {} for f in d.get("features") or []]
        if not batch: break
        rows.extend(batch); offset+=len(batch)
    return count,rows

def _epoch(v):
    if v in (None,""): return None
    try:return datetime.fromtimestamp(float(v)/1000,timezone.utc).date().isoformat()
    except Exception:return str(v)

def _columns(c,table):
    cur=execute(c,f"SELECT * FROM {table} LIMIT 0")
    return [d[0] for d in cur.description]

def _insert(c,table,cols,row):
    use=[k for k in row if k in cols]
    execute(c,f"INSERT INTO {table} ("+",".join(use)+") VALUES ("+",".join(["?"]*len(use))+")",
            tuple(row[k] for k in use))

def refresh_suffolk_live_evidence_v16e4():
    owner_count,owners=_fetch_all(*SOURCES["owner"])
    transfer_count,transfers=_fetch_all(*SOURCES["transfer"])
    if len(owners)!=owner_count or len(transfers)!=transfer_count:
        raise RuntimeError(f"incomplete acquisition owner {len(owners)}/{owner_count}, transfer {len(transfers)}/{transfer_count}")
    if not all(str(x.get("PARCELID","")).startswith("0905") for x in owners+transfers):
        raise RuntimeError("parcel prefix guard failed")

    c=connect()
    try:
        members={str(r[0]) for r in execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=?",(MARKET,)).fetchall()}
        if len(members)!=2082: raise RuntimeError(f"membership guard failed: {len(members)}")
        owners=[x for x in owners if str(x.get("PARCELID")) in members]
        transfers=[x for x in transfers if str(x.get("PARCELID")) in members]

        oc=_columns(c,"ownership_evidence"); tc=_columns(c,"transfers")
        # ObjectID is the immutable source observation identity when available.
        owner_ids=set()
        if "source_record_id" in oc:
            owner_ids={str(r[0]) for r in execute(c,"SELECT source_record_id FROM ownership_evidence WHERE source_record_id IS NOT NULL").fetchall()}
        transfer_ids=set()
        if "source_record_id" in tc:
            transfer_ids={str(r[0]) for r in execute(c,"SELECT source_record_id FROM transfers WHERE source_record_id IS NOT NULL").fetchall()}

        new_o=[]; new_t=[]
        for x in owners:
            sid=str(x.get("OBJECTID"))
            if sid in owner_ids: continue
            new_o.append({"parcel_id":str(x.get("PARCELID")),"owner_name":x.get("OWNERNAME"),
              "first_name":x.get("FIRSTNAME"),"last_name":x.get("LASTNAME"),
              "source_record_id":sid,"source":"Suffolk TaxParcelOwner"})
        for x in transfers:
            sid=str(x.get("OBJECTID"))
            if sid in transfer_ids: continue
            new_t.append({"parcel_id":str(x.get("PARCELID")),"liber_page":x.get("LIBERPAGE"),
              "record_date":_epoch(x.get("RECORDDATE")),"document_number":x.get("DOCNUM"),
              "document_code":x.get("DOCCODE"),"document_date":_epoch(x.get("DOCDATE")),
              "entry_date":_epoch(x.get("ENTRYDATE")),"history_sequence":x.get("TRANSHISSEQ"),
              "source_record_id":sid,"source":"Suffolk TaxParcelTransferHistory"})
        for x in new_o:_insert(c,"ownership_evidence",oc,x)
        for x in new_t:_insert(c,"transfers",tc,x)
        c.commit()
        return {"status":"ok","version":VERSION,"mode":MODE,
          "acquisition":{"owner_count_official":owner_count,"owner_rows_acquired":len(owners),
                         "transfer_count_official":transfer_count,"transfer_rows_acquired":len(transfers),
                         "filter":"PARCELID LIKE '0905%'","complete":True},
          "persistence":{"new_owner_rows":len(new_o),"new_transfer_rows":len(new_t),
                         "new_source_rows_total":len(new_o)+len(new_t)},
          "guards":{"market_membership":len(members),"parcel_prefix_guard":True,
                    "seller_intent_inferred":False,"seller_scoring":False,
                    "contact_authorized":False,"outreach_touched":False},
          "pipeline":{"next":"RUN_V16A_EVIDENCE_MEMORY","then":"V16B_CHANGE_DETECTION -> V16C -> V16D"},
          "interpretation":"New source rows are factual observations, not seller leads."}
    except Exception:
        c.rollback(); raise
    finally:c.close()
