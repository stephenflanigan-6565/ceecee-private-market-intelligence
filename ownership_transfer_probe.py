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
TRANSFER_HISTORY=BASE+"/TaxParcelTransferHistory/FeatureServer/0/query"
DISTRICT_PREFIX="0905"
PAGE=1000

def utc(): return datetime.now(timezone.utc).isoformat()

def canonical_ids():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id FROM properties WHERE district=? AND status='A'",("0905",)).fetchall()
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
        row=execute(c,"SELECT parcel_id FROM properties WHERE district=? AND status='A' ORDER BY parcel_id LIMIT 1",("0905",)).fetchone()
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


def probe_transfer_history_handshake():
    """V15G bounded one-parcel TaxParcelTransferHistory handshake. Read-only, no party names, no DB writes."""
    pid=_one_canonical_id()
    data=fetch(TRANSFER_HISTORY,{
        "where":f"PARCELID = '{pid}'",
        "outFields":"PARCELID,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ",
        "returnGeometry":"false",
        "resultRecordCount":5,
        "orderByFields":"TRANSHISSEQ DESC",
        "f":"json"
    })
    feats=data.get("features",[])
    attrs=[x.get("attributes",{}) for x in feats]
    r=_base("READ_ONLY_TRANSFER_HISTORY_HANDSHAKE")
    r.update({
        "source":"Suffolk County TaxParcelTransferHistory",
        "probe_parcel_id":pid,
        "records_returned":len(attrs),
        "max_records_requested":5,
        "party_names_requested":False,
        "party_names_exposed_in_response":False,
        "bounded_probe":True,
        "records":[{k:a.get(k) for k in ("PARCELID","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ")} for a in attrs]
    })
    return r

# V15H diagnostic constants
PARCEL_CONTROL=BASE+"/TaxParcelPolygon/FeatureServer/0/query"

def _diagnostic_call(label, url, params, timeout=10):
    """Run one bounded upstream call and always return structured diagnostics."""
    import time
    started=time.monotonic()
    u=url+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(u,headers={"User-Agent":"Private-Market-Intelligence/15H","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            raw=resp.read()
            http_status=getattr(resp,"status",200)
        elapsed=round(time.monotonic()-started,3)
        try:
            data=json.loads(raw.decode("utf-8"))
        except Exception as e:
            return {"label":label,"ok":False,"stage":"JSON_PARSE","http_status":http_status,
                    "elapsed_seconds":elapsed,"error_type":type(e).__name__,"response_bytes":len(raw)}
        if "error" in data:
            err=data.get("error") or {}
            return {"label":label,"ok":False,"stage":"ARCGIS_RESPONSE","http_status":http_status,
                    "elapsed_seconds":elapsed,"arcgis_code":err.get("code"),
                    "arcgis_message":str(err.get("message",""))[:160]}
        feats=data.get("features",[])
        return {"label":label,"ok":True,"stage":"COMPLETE","http_status":http_status,
                "elapsed_seconds":elapsed,"records_returned":len(feats),
                "exceeded_transfer_limit":bool(data.get("exceededTransferLimit"))}
    except urllib.error.HTTPError as e:
        return {"label":label,"ok":False,"stage":"HTTP","http_status":e.code,
                "elapsed_seconds":round(time.monotonic()-started,3),"error_type":"HTTPError"}
    except urllib.error.URLError as e:
        return {"label":label,"ok":False,"stage":"NETWORK",
                "elapsed_seconds":round(time.monotonic()-started,3),"error_type":"URLError",
                "reason_type":type(getattr(e,"reason",None)).__name__}
    except Exception as e:
        return {"label":label,"ok":False,"stage":"UNEXPECTED",
                "elapsed_seconds":round(time.monotonic()-started,3),"error_type":type(e).__name__,
                "error":str(e)[:160]}

def probe_internal_failure_isolation():
    """V15H: prove each common stage without writes; route must return HTTP 200 even on diagnostic failure."""
    result=_base("READ_ONLY_INTERNAL_FAILURE_ISOLATION")
    result.update({"version":"V15H","diagnostic_http_status_policy":"ALWAYS_200",
                   "canonical_lookup":{"ok":False},"tests":[]})
    try:
        pid=_one_canonical_id()
        result["canonical_lookup"]={"ok":True,"parcel_id":pid}
    except Exception as e:
        result["status"]="diagnostic_failure"
        result["canonical_lookup"]={"ok":False,"error_type":type(e).__name__,"error":str(e)[:160]}
        return result

    common={"where":f"PARCELID = '{pid}'","returnGeometry":"false","resultRecordCount":1,"f":"json"}
    p=dict(common); p["outFields"]="PARCELID"
    result["tests"].append(_diagnostic_call("PARCEL_CONTROL",PARCEL_CONTROL,p))

    p=dict(common); p["outFields"]="PARCELID"
    result["tests"].append(_diagnostic_call("OWNER",OWNER,p))

    p=dict(common); p.update({"outFields":"PARCELID,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ",
                              "resultRecordCount":5,"orderByFields":"TRANSHISSEQ DESC"})
    result["tests"].append(_diagnostic_call("TRANSFER_HISTORY",TRANSFER_HISTORY,p))

    result["all_upstream_tests_ok"]=all(x.get("ok") for x in result["tests"])
    result["status"]="ok" if result["all_upstream_tests_ok"] else "diagnostic_complete_with_failure"
    return result

# V15I read-only ownership + transfer-history coverage measurement.
def _fetch_paged_parcel_ids(url, page_size=2000, extra_fields=None):
    """Fetch only parcel identity (+ optional small fields) in bounded ArcGIS pages."""
    import time
    fields=["PARCELID"] + list(extra_fields or [])
    out=[]; offset=0; pages=0; elapsed_total=0.0
    while True:
        started=time.monotonic()
        data=fetch(url,{
            "where":f"PARCELID LIKE '{DISTRICT_PREFIX}%'",
            "outFields":",".join(fields),
            "returnGeometry":"false",
            "resultOffset":offset,
            "resultRecordCount":page_size,
            "orderByFields":"PARCELID",
            "f":"json"
        })
        elapsed_total += time.monotonic()-started
        feats=data.get("features",[]); pages += 1
        out.extend(x.get("attributes",{}) for x in feats)
        if not feats: break
        if len(feats) < page_size and not data.get("exceededTransferLimit"): break
        offset += len(feats)
        if pages >= 50: raise RuntimeError("V15I_PAGE_SAFETY_LIMIT")
    return out,pages,round(elapsed_total,3)

def probe_coverage_v15i():
    """Measure source coverage across locked Westhampton universe. No writes, no names."""
    c=connect()
    try:
        rows=execute(c,"""SELECT p.parcel_id, COALESCE(pc.cohort,'UNCLASSIFIED')
                          FROM properties p
                          LEFT JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
                          WHERE p.district=? AND p.status='A' ORDER BY p.parcel_id""",("0905",)).fetchall()
        cohort_by_pid={str(r[0]):str(r[1]) for r in rows}
    finally:
        c.close()
    canonical=set(cohort_by_pid)
    residential={pid for pid,cohort in cohort_by_pid.items() if cohort in ("RESIDENTIAL_IMPROVED","RESIDENTIAL_VACANT_LAND")}

    owners,owner_pages,owner_seconds=_fetch_paged_parcel_ids(OWNER,2000)
    owner_counts={}
    for a in owners:
        pid=a.get("PARCELID")
        if pid is not None:
            pid=str(pid); owner_counts[pid]=owner_counts.get(pid,0)+1
    owner_match=set(owner_counts)&canonical

    hist,hist_pages,hist_seconds=_fetch_paged_parcel_ids(TRANSFER_HISTORY,2000,["TRANSHISSEQ"])
    hist_counts={}
    for a in hist:
        pid=a.get("PARCELID")
        if pid is not None:
            pid=str(pid); hist_counts[pid]=hist_counts.get(pid,0)+1
    hist_match=set(hist_counts)&canonical

    owner_missing=sorted(canonical-owner_match)
    owner_multi=sorted(pid for pid,n in owner_counts.items() if pid in canonical and n>1)
    hist_missing=sorted(canonical-hist_match)
    both=owner_match & hist_match
    residential_owner=owner_match & residential
    residential_hist=hist_match & residential

    def pct(n,d): return round((100.0*n/d),2) if d else 0.0
    result=_base("READ_ONLY_OWNERSHIP_TRANSFER_COVERAGE")
    result.update({
        "version":"V15I","status":"ok","canonical_active_parcels":len(canonical),
        "residential_side_parcels":len(residential),
        "owner_source":{"records_fetched":len(owners),"pages":owner_pages,"elapsed_seconds":owner_seconds,
                        "parcels_with_record":len(owner_match),"coverage_pct":pct(len(owner_match),len(canonical)),
                        "parcels_without_record":len(owner_missing),"parcels_with_multiple_records":len(owner_multi),
                        "residential_parcels_with_record":len(residential_owner),
                        "residential_coverage_pct":pct(len(residential_owner),len(residential)),
                        "missing_sample_parcel_ids":owner_missing[:10],"multiple_record_sample_parcel_ids":owner_multi[:10],
                        "owner_names_requested":False,"owner_names_exposed_in_response":False},
        "transfer_history_source":{"records_fetched":len(hist),"pages":hist_pages,"elapsed_seconds":hist_seconds,
                        "parcels_with_history":len(hist_match),"coverage_pct":pct(len(hist_match),len(canonical)),
                        "parcels_without_history":len(hist_missing),
                        "residential_parcels_with_history":len(residential_hist),
                        "residential_coverage_pct":pct(len(residential_hist),len(residential)),
                        "history_records_per_covered_parcel":{"min":min((hist_counts[p] for p in hist_match),default=0),
                            "max":max((hist_counts[p] for p in hist_match),default=0),
                            "average":round(sum(hist_counts[p] for p in hist_match)/len(hist_match),2) if hist_match else 0},
                        "missing_sample_parcel_ids":hist_missing[:10],"party_names_requested":False,"party_names_exposed_in_response":False},
        "combined":{"parcels_with_owner_and_history":len(both),"coverage_pct":pct(len(both),len(canonical)),
                    "residential_with_owner_and_history":len(both & residential),
                    "residential_coverage_pct":pct(len(both & residential),len(residential))},
        "classification_method_expected":"V15D_ORPTS_BROAD_COHORT_V1",
        "measurement_only":True,"permanent_ingestion_performed":False
    })
    return result
