#!/usr/bin/env python3
"""V16E2 — exact Suffolk query-shape isolation. Diagnostic only; zero DB writes."""
import json, urllib.parse, urllib.request, urllib.error, time

VERSION="V16E2"
MODE="SUFFOLK_EXACT_QUERY_SHAPE_ISOLATION"
BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; PrivateMarketIntelligence/16E2)",
         "Accept":"application/json,text/plain,*/*"}

TESTS=[
 ("owner_control",f"{BASE}/TaxParcelOwner/FeatureServer/0/query",
  {"where":"1=1","outFields":"*","returnGeometry":"false","resultRecordCount":"1","f":"json"}),
 ("owner_district",f"{BASE}/TaxParcelOwner/FeatureServer/0/query",
  {"where":"DISTRICT = '0905'","outFields":"*","returnGeometry":"false","resultRecordCount":"1","f":"json"}),
 ("owner_parcel_like",f"{BASE}/TaxParcelOwner/FeatureServer/0/query",
  {"where":"PARCELID LIKE '0905%'","outFields":"*","returnGeometry":"false","resultRecordCount":"1","f":"json"}),
 ("transfer_control",f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query",
  {"where":"1=1","outFields":"*","returnGeometry":"false","resultRecordCount":"1","f":"json"}),
 ("transfer_district",f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query",
  {"where":"DISTRICT = '0905'","outFields":"*","returnGeometry":"false","resultRecordCount":"1","f":"json"}),
 ("transfer_parcel_like",f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query",
  {"where":"PARCELID LIKE '0905%'","outFields":"*","returnGeometry":"false","resultRecordCount":"1","f":"json"}),
]

def _probe(name,url,params):
    target=url+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(target,headers=HEADERS,method="GET")
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            raw=r.read(12000).decode("utf-8","replace")
            parsed=json.loads(raw)
            feats=parsed.get("features") or []
            attrs=(feats[0].get("attributes") if feats else {}) or {}
            return {"test":name,"ok":not bool(parsed.get("error")),"http_status":r.status,
                    "elapsed_ms":round((time.time()-t)*1000),"arcgis_error":parsed.get("error"),
                    "feature_count_returned":len(feats),"returned_fields":sorted(attrs.keys())}
    except urllib.error.HTTPError as e:
        body=e.read(1200).decode("utf-8","replace")
        return {"test":name,"ok":False,"http_status":e.code,
                "elapsed_ms":round((time.time()-t)*1000),"error":"HTTPError",
                "response_excerpt":body[:500]}
    except Exception as e:
        return {"test":name,"ok":False,"elapsed_ms":round((time.time()-t)*1000),
                "error":type(e).__name__,"detail":str(e)[:500]}

def diagnose_suffolk_query_shape_v16e2():
    results=[_probe(*t) for t in TESTS]
    by={r["test"]:r for r in results}
    owner_ok=[k for k in ("owner_district","owner_parcel_like") if by[k].get("ok")]
    transfer_ok=[k for k in ("transfer_district","transfer_parcel_like") if by[k].get("ok")]
    return {"status":"ok","version":VERSION,"mode":MODE,"writes_performed":0,
      "tests":results,
      "summary":{"tests_run":len(results),"owner_filtered_paths_working":owner_ok,
                 "transfer_filtered_paths_working":transfer_ok},
      "guards":{"database_writes":False,"seller_intent_inferred":False,"seller_scoring":False,
                "contact_authorized":False,"outreach_touched":False},
      "decision":"BUILD_REFRESH_FROM_PROVEN_FILTER_SHAPE" if owner_ok and transfer_ok else
                 "FILTER_OR_SCHEMA_STILL_UNPROVEN_DO_NOT_WRITE"}
