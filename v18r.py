#!/usr/bin/env python3
"""V18R — execute exact V18Q targeted Suffolk GIS metadata recheck. Read-only."""
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

VERSION="V18R"
GIS_URL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"

def _norm_id(v):
    s=str(v or "").strip()
    return s[:-2] if s.endswith(".0") else s

def _epoch_iso(v):
    if v in (None,""): return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(v)/1000.0, tz=timezone.utc).date().isoformat()
    except Exception:
        return v

def _query(parcel_id):
    params={
      "where": "PARCELID='{}'".format(parcel_id.replace("'","''")),
      "outFields":"PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ",
      "returnGeometry":"false",
      "orderByFields":"RECORDDATE ASC,TRANSHISSEQ ASC",
      "resultRecordCount":"2000",
      "f":"json"
    }
    req=Request(GIS_URL+"?"+urlencode(params),headers={"User-Agent":"Private-Market-Intelligence/1.0 factual-research"})
    with urlopen(req,timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def build_v18r():
    jobs=json.loads((Path(__file__).with_name("v18r_donor.json")).read_text())["verification_jobs"]
    results=[]; query_errors=0
    for job in jobs:
        pid=job["parcel_id"]
        try:
            raw=_query(pid)
            if raw.get("error"):
                raise RuntimeError(str(raw["error"]))
            feats=[f.get("attributes",{}) for f in raw.get("features",[])]
            parcel_result={"parcel_id":pid,"query_status":"OK","requested_identity_count":job["unresolved_identity_count"],"identity_results":[]}
            for target in job["unresolved_source_identities"]:
                sid=_norm_id(target["source_record_id"])
                matches=[a for a in feats if _norm_id(a.get("DOCNUM"))==sid]
                if not matches:
                    parcel_result["identity_results"].append({
                      "source_record_id":target["source_record_id"],"state":"IDENTITY_NOT_FOUND",
                      "requested_missing_fields":target["missing_fields"],"returned":None})
                    continue
                a=matches[0]
                returned={"parcel_id":a.get("PARCELID"),"source_record_id":str(a.get("DOCNUM")) if a.get("DOCNUM") is not None else None,
                  "doccode":a.get("DOCCODE"),"recorddate":_epoch_iso(a.get("RECORDDATE")),
                  "docdate":_epoch_iso(a.get("DOCDATE")),"entrydate":_epoch_iso(a.get("ENTRYDATE")),
                  "liberpage":a.get("LIBERPAGE"),"transfer_history_sequence":a.get("TRANSHISSEQ")}
                still=[]
                for f in target["missing_fields"]:
                    key={"RECORDDATE":"recorddate","LIBERPAGE":"liberpage","DOCCODE":"doccode"}[f]
                    if returned.get(key) in (None,""): still.append(f)
                state="METADATA_COMPLETED" if not still else "STILL_INCOMPLETE"
                parcel_result["identity_results"].append({
                  "source_record_id":target["source_record_id"],"state":state,
                  "requested_missing_fields":target["missing_fields"],"still_missing_fields":still,
                  "returned":returned})
            results.append(parcel_result)
        except Exception as e:
            query_errors+=1
            results.append({"parcel_id":pid,"query_status":"ERROR","error_type":type(e).__name__,
              "error":str(e)[:500],"requested_identity_count":job["unresolved_identity_count"],"identity_results":[]})
    flat=[i for p in results for i in p["identity_results"]]
    states={}
    for x in flat: states[x["state"]]=states.get(x["state"],0)+1
    completed=sum(1 for x in flat if x["state"]=="METADATA_COMPLETED")
    incomplete=sum(1 for x in flat if x["state"]=="STILL_INCOMPLETE")
    missing=sum(1 for x in flat if x["state"]=="IDENTITY_NOT_FOUND")
    return {"status":"ok" if query_errors==0 else "partial","version":VERSION,
      "mode":"EXACT_V18Q_10_IDENTITY_TARGETED_SUFFOLK_GIS_RECHECK_READ_ONLY",
      "summary":{"verification_properties":len(jobs),"requested_source_identities":sum(j["unresolved_identity_count"] for j in jobs),
        "identity_results_returned":len(flat),"metadata_completed":completed,"still_incomplete":incomplete,
        "identity_not_found":missing,"state_counts":states,"query_errors":query_errors,"database_writes":0},
      "purpose":"Execute only the exact V18Q authoritative GIS rechecks and determine which metadata gaps the machine can resolve.",
      "results":results,
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
