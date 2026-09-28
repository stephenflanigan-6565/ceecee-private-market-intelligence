#!/usr/bin/env python3
"""V16E1 — Suffolk source access isolation. Diagnostic only: zero DB writes."""
import json, urllib.parse, urllib.request, urllib.error, time

VERSION="V16E1"
MODE="SUFFOLK_SOURCE_ACCESS_ISOLATION"
BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
SOURCES=[
 ("owner_feature",f"{BASE}/TaxParcelOwner/FeatureServer/0/query"),
 ("owner_map",f"{BASE}/TaxParcelOwner/MapServer/0/query"),
 ("transfer_feature",f"{BASE}/TaxParcelTransferHistory/FeatureServer/0/query"),
 ("transfer_map",f"{BASE}/TaxParcelTransferHistory/MapServer/0/query"),
]
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; PrivateMarketIntelligence/16E1)",
         "Accept":"application/json,text/plain,*/*"}

def _probe(name,url,method):
    params={"where":"1=1","returnCountOnly":"true","f":"json"}
    body=urllib.parse.urlencode(params).encode()
    req=urllib.request.Request(url, data=body if method=="POST" else None,
                               headers=HEADERS, method=method)
    target=url if method=="POST" else url+"?"+urllib.parse.urlencode(params)
    if method=="GET": req=urllib.request.Request(target,headers=HEADERS,method="GET")
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            raw=r.read(4096).decode("utf-8","replace")
            parsed=json.loads(raw)
            return {"source":name,"transport":method,"ok":not bool(parsed.get("error")),
                    "http_status":r.status,"elapsed_ms":round((time.time()-t)*1000),
                    "arcgis_error":parsed.get("error"),"count":parsed.get("count")}
    except urllib.error.HTTPError as e:
        body=e.read(1000).decode("utf-8","replace")
        return {"source":name,"transport":method,"ok":False,"http_status":e.code,
                "elapsed_ms":round((time.time()-t)*1000),"error":"HTTPError",
                "response_excerpt":body[:300]}
    except Exception as e:
        return {"source":name,"transport":method,"ok":False,
                "elapsed_ms":round((time.time()-t)*1000),"error":type(e).__name__,
                "detail":str(e)[:300]}

def diagnose_suffolk_source_access_v16e1():
    tests=[]
    for name,url in SOURCES:
        for method in ("GET","POST"):
            tests.append(_probe(name,url,method))
    working=[x for x in tests if x.get("ok")]
    return {"status":"ok","version":VERSION,"mode":MODE,
      "purpose":"ISOLATE_SOURCE_ACCESS_BEFORE_ANY_REFRESH_WRITE",
      "writes_performed":0,
      "tests":tests,
      "summary":{"tests_run":len(tests),"working_paths":len(working),
                 "working":[{"source":x["source"],"transport":x["transport"],
                             "http_status":x.get("http_status"),"count":x.get("count")} for x in working]},
      "guards":{"database_writes":False,"seller_intent_inferred":False,"seller_scoring":False,
                "contact_authorized":False,"outreach_touched":False},
      "decision":"USE_ONLY_A_PROVEN_WORKING_OFFICIAL_PATH_IN_NEXT_REFRESH_BUILD" if working else
                 "NO_WORKING_OFFICIAL_PATH_FROM_RUNTIME_DO_NOT_BUILD_REFRESH"}
