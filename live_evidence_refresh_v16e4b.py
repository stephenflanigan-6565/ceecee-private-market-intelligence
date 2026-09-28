#!/usr/bin/env python3
"""V16E4b — transfer observed_at schema repair.
Exact repair for V16E4a failure. Acquisition and protected pipeline unchanged.
"""
import json, urllib.parse, urllib.request
from datetime import datetime, timezone
from db import connect, execute
VERSION="V16E4b"; MODE="SUFFOLK_LIVE_EVIDENCE_REFRESH_TRANSFER_OBSERVED_AT_REPAIR"
MARKET="WESTHAMPTON_BEACH_NY"
BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; PrivateMarketIntelligence/16E4b)","Accept":"application/json,text/plain,*/*"}
SOURCES={"owner":(f"{BASE}/TaxParcelOwner/FeatureServer/0/query","OBJECTID,PARCELID,FIRSTNAME,LASTNAME,OWNERNAME"),
"transfer":(f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query","OBJECTID,PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ")}
def _call(url,p):
    req=urllib.request.Request(url+"?"+urllib.parse.urlencode(p),headers=HEADERS)
    with urllib.request.urlopen(req,timeout=30) as r:d=json.loads(r.read().decode())
    if d.get("error"):raise RuntimeError(str(d["error"]))
    return d
def _fetch(url,fields):
    q="PARCELID LIKE '0905%'"; n=int(_call(url,{"where":q,"returnCountOnly":"true","f":"json"}).get("count") or 0)
    rows=[];off=0
    while off<n:
        d=_call(url,{"where":q,"outFields":fields,"returnGeometry":"false","orderByFields":"OBJECTID","resultOffset":off,"resultRecordCount":1000,"f":"json"})
        b=[f.get("attributes") or {} for f in d.get("features") or []]
        if not b:break
        rows+=b;off+=len(b)
    if len(rows)!=n:raise RuntimeError(f"incomplete acquisition {len(rows)}/{n}")
    return rows
def _date(v):
    if v in (None,""):return None
    try:return datetime.fromtimestamp(float(v)/1000,timezone.utc).date().isoformat()
    except:return str(v)
def _cols(c,t):
    cur=execute(c,f"SELECT * FROM {t} LIMIT 0");return [d[0] for d in cur.description]
def _insert(c,t,cols,row):
    use=[k for k in row if k in cols]
    execute(c,f"INSERT INTO {t} ("+",".join(use)+") VALUES ("+",".join(["?"]*len(use))+")",tuple(row[k] for k in use))
def refresh_suffolk_live_evidence_v16e4b():
    observed_at=datetime.now(timezone.utc).isoformat()
    owners=_fetch(*SOURCES["owner"]);transfers=_fetch(*SOURCES["transfer"])
    if not all(str(x.get("PARCELID","")).startswith("0905") for x in owners+transfers):raise RuntimeError("prefix guard failed")
    c=connect()
    try:
        members={str(r[0]) for r in execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=?",(MARKET,)).fetchall()}
        if len(members)!=2082:raise RuntimeError(f"membership guard failed {len(members)}")
        owners=[x for x in owners if str(x.get("PARCELID")) in members];transfers=[x for x in transfers if str(x.get("PARCELID")) in members]
        oc=_cols(c,"ownership_evidence");tc=_cols(c,"transfers")
        if "source_object_id" not in oc:raise RuntimeError("ownership_evidence missing source_object_id")
        if "observed_at" not in tc:raise RuntimeError("transfers missing observed_at")
        oi={str(r[0]) for r in execute(c,"SELECT source_object_id FROM ownership_evidence WHERE source_object_id IS NOT NULL").fetchall()}
        ti_col="source_object_id" if "source_object_id" in tc else ("source_record_id" if "source_record_id" in tc else None)
        ti={str(r[0]) for r in execute(c,f"SELECT {ti_col} FROM transfers WHERE {ti_col} IS NOT NULL").fetchall()} if ti_col else set()
        new_o=[];new_t=[]
        for x in owners:
            sid=str(x.get("OBJECTID"))
            if sid in oi:continue
            row={"parcel_id":str(x.get("PARCELID")),"owner_name":x.get("OWNERNAME"),"first_name":x.get("FIRSTNAME"),
                 "last_name":x.get("LASTNAME"),"source_object_id":sid,"source":"Suffolk TaxParcelOwner"}
            if "observed_at" in oc:row["observed_at"]=observed_at
            new_o.append(row)
        for x in transfers:
            sid=str(x.get("OBJECTID"))
            if ti_col and sid in ti:continue
            row={"parcel_id":str(x.get("PARCELID")),"liber_page":x.get("LIBERPAGE"),"record_date":_date(x.get("RECORDDATE")),
                 "document_number":x.get("DOCNUM"),"document_code":x.get("DOCCODE"),"document_date":_date(x.get("DOCDATE")),
                 "entry_date":_date(x.get("ENTRYDATE")),"history_sequence":x.get("TRANSHISSEQ"),
                 "source":"Suffolk TaxParcelTransferHistory","observed_at":observed_at}
            if ti_col:row[ti_col]=sid
            new_t.append(row)
        for x in new_o:_insert(c,"ownership_evidence",oc,x)
        for x in new_t:_insert(c,"transfers",tc,x)
        c.commit()
        return {"status":"ok","version":VERSION,"mode":MODE,
          "acquisition":{"owner_rows_in_market":len(owners),"transfer_rows_in_market":len(transfers),"complete":True},
          "persistence":{"new_owner_rows":len(new_o),"new_transfer_rows":len(new_t),"new_source_rows_total":len(new_o)+len(new_t)},
          "schema_repair":{"ownership_identity_column":"source_object_id","transfer_observed_at_populated":True,
                           "observation_timestamp":observed_at,"transfer_identity_column":ti_col},
          "guards":{"market_membership":len(members),"atomic_transaction":True,"seller_intent_inferred":False,
                    "seller_scoring":False,"contact_authorized":False,"outreach_touched":False},
          "pipeline":{"next":"RUN_V16A_EVIDENCE_MEMORY","then":"V16B -> V16C -> V16D"}}
    except Exception:
        c.rollback();raise
    finally:c.close()
