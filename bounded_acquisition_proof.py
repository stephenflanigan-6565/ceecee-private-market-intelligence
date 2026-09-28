#!/usr/bin/env python3
"""V16E3 — Suffolk bounded acquisition proof. Read-only; zero DB writes."""
import json, urllib.parse, urllib.request, urllib.error, time

VERSION="V16E3"
MODE="SUFFOLK_BOUNDED_ACQUISITION_PROOF"
BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; PrivateMarketIntelligence/16E3)",
         "Accept":"application/json,text/plain,*/*"}
SOURCES=[
 ("owner",f"{BASE}/TaxParcelOwner/FeatureServer/0/query",
  "OBJECTID,PARCELID,FIRSTNAME,LASTNAME,OWNERNAME"),
 ("transfer",f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query",
  "OBJECTID,PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ"),
]

def _call(url, params):
    target=url+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(target,headers=HEADERS,method="GET")
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.status,json.loads(r.read().decode("utf-8","replace"))

def _probe(name,url,fields):
    where="PARCELID LIKE '0905%'"
    t=time.time()
    count_status,count_data=_call(url,{"where":where,"returnCountOnly":"true","f":"json"})
    if count_data.get("error"): raise RuntimeError(f"{name} count: {count_data['error']}")
    count=int(count_data.get("count") or 0)
    sample_status,sample=_call(url,{"where":where,"outFields":fields,"returnGeometry":"false",
                                    "orderByFields":"OBJECTID","resultOffset":"0",
                                    "resultRecordCount":"100","f":"json"})
    if sample.get("error"): raise RuntimeError(f"{name} sample: {sample['error']}")
    feats=sample.get("features") or []
    attrs=[f.get("attributes") or {} for f in feats]
    pids={str(a.get("PARCELID")) for a in attrs if a.get("PARCELID") is not None}
    prefix_ok=all(p.startswith("0905") for p in pids)
    return {"source":name,"ok":True,"filter":where,"count":count,
            "sample_records_requested":100,"sample_records_returned":len(attrs),
            "sample_unique_parcels":len(pids),"parcel_prefix_guard_passed":prefix_ok,
            "first_objectid":attrs[0].get("OBJECTID") if attrs else None,
            "last_objectid":attrs[-1].get("OBJECTID") if attrs else None,
            "http_status_count":count_status,"http_status_sample":sample_status,
            "elapsed_ms":round((time.time()-t)*1000)}

def prove_suffolk_bounded_acquisition_v16e3():
    results=[]
    try:
        for s in SOURCES: results.append(_probe(*s))
        ok=all(r.get("ok") and r.get("parcel_prefix_guard_passed") and r.get("sample_records_returned")>0 for r in results)
        return {"status":"ok" if ok else "degraded","version":VERSION,"mode":MODE,
          "writes_performed":0,"results":results,
          "guards":{"database_writes":False,"bounded_to_parcel_prefix_0905":True,
                    "seller_intent_inferred":False,"seller_scoring":False,
                    "contact_authorized":False,"outreach_touched":False},
          "decision":"ACQUISITION_SHAPE_PROVEN_READY_FOR_PERSISTENCE_REPAIR" if ok else
                     "DO_NOT_ENABLE_PERSISTENCE"}
    except Exception as e:
        return {"status":"degraded","version":VERSION,"mode":MODE,"writes_performed":0,
                "error_type":type(e).__name__,"error":str(e)[:500],
                "decision":"DO_NOT_ENABLE_PERSISTENCE"}
