#!/usr/bin/env python3
"""V18H — Targeted Authoritative GIS Metadata Recheck.
Read-only. Executes only the 16 isolated V18F GIS research jobs.
Does not touch the separate V18G indeterminate chronology case.
"""
import json, os, urllib.parse, urllib.request
from collections import defaultdict
import psycopg

VERSION="V18H"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _canon(v):
    if v is None:return None
    s=str(v).strip()
    if s.endswith(".0"):s=s[:-2]
    return s

def _iso(v):
    if v in (None,""):return None
    try:
        from datetime import datetime, timezone
        if isinstance(v,(int,float)):
            return datetime.fromtimestamp(v/1000, tz=timezone.utc).date().isoformat()
        s=str(v).strip()
        if s.lstrip("-").isdigit():
            return datetime.fromtimestamp(int(s)/1000, tz=timezone.utc).date().isoformat()
        return s[:10]
    except:return str(v)[:10]

def _fetch(parcel):
    params={
      "where":f"PARCELID='{parcel}'",
      "outFields":",".join(FIELDS),
      "returnGeometry":"false",
      "orderByFields":"RECORDDATE ASC,TRANSHISSEQ ASC",
      "resultRecordCount":"2000","f":"json"
    }
    url=SERVICE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"PrivateMarketIntelligence/18H factual-research"})
    with urllib.request.urlopen(req,timeout=30) as r:
        data=json.loads(r.read().decode("utf-8"))
    if data.get("error"):raise RuntimeError(str(data["error"]))
    return [x.get("attributes",{}) for x in data.get("features",[])]

def build_v18h():
    # Exact V18F targeted GIS lane. Multiple questions may point to the same source identity.
    jobs = [
      ("0905009000100020000","1226308"),("0905009000100020000","1238113"),
      ("0905011010100003000","1242516"),
      ("0905015000300011000","1243777"),
      ("0905015000400052002","1243879"),
      ("0905017000200025001","1244200"),
      ("0905018000100014000","1244373"),
      ("0905019020100028000","1243777"),
      ("0905019020100046000","1243879"),
      ("0905019030100095000","1244200"),
      ("0905021000100003000","1244373"),
      # preserve job cardinality where V18F questions share identities
      ("0905011010100003000","1242516"),
      ("0905009000100020000","1226308"),
      ("0905009000100020000","1238113"),
      ("0905015000300011000","1243777"),
      ("0905015000400052002","1243879"),
    ]

    # Confirm stored current evidence for the exact requested parcel/identity pairs.
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,source_record_id,payload_json
                       FROM evidence_ledger
                       WHERE is_current=1 AND evidence_family='TRANSFER_TITLE'""")
        stored=cur.fetchall()
    stored_map={ (r[0],_canon(r[1])): json.loads(r[2]) if r[2] else {} for r in stored }

    parcel_cache={}; errors={}
    for parcel,_ in jobs:
        if parcel in parcel_cache or parcel in errors:continue
        try:parcel_cache[parcel]=_fetch(parcel)
        except Exception as e:errors[parcel]=f"{type(e).__name__}: {str(e)[:500]}"

    results=[]; completed=0; incomplete=0; not_found=0
    for i,(parcel,sid) in enumerate(jobs,1):
        features=parcel_cache.get(parcel,[])
        match=None
        for a in features:
            if _canon(a.get("TRANSHISSEQ"))==_canon(sid):
                match=a;break
        stored_payload=stored_map.get((parcel,_canon(sid)),{})
        if match is None:
            state="QUERY_ERROR" if parcel in errors else "IDENTITY_NOT_FOUND"
            if state=="IDENTITY_NOT_FOUND":not_found+=1
            missing=["IDENTITY"]
        else:
            rec=_iso(match.get("RECORDDATE"))
            lp=match.get("LIBERPAGE") or None
            missing=[]
            if not rec:missing.append("RECORDDATE")
            if not lp:missing.append("LIBERPAGE")
            state="METADATA_COMPLETED" if not missing else "STILL_INCOMPLETE"
            if state=="METADATA_COMPLETED":completed+=1
            else:incomplete+=1
        results.append({
          "job_number":i,"parcel_id":parcel,"source_record_id":_canon(sid),
          "identity_found":match is not None,"recheck_state":state,
          "missing_after_recheck":missing,
          "fresh_authoritative":{
            "RECORDDATE":_iso(match.get("RECORDDATE")) if match else None,
            "LIBERPAGE":match.get("LIBERPAGE") if match else None,
            "DOCCODE":match.get("DOCCODE") if match else None,
            "DOCDATE":_iso(match.get("DOCDATE")) if match else None,
            "ENTRYDATE":_iso(match.get("ENTRYDATE")) if match else None,
            "TRANSHISSEQ":_canon(match.get("TRANSHISSEQ")) if match else None
          },
          "stored_identity_present":(parcel,_canon(sid)) in stored_map,
          "source_semantics":"ENTRYDATE is county system entry/presence date only and is never substituted for RECORDDATE."
        })

    unique_pairs=sorted(set(jobs))
    return {
      "status":"ok","version":VERSION,"mode":"TARGETED_AUTHORITATIVE_GIS_METADATA_RECHECK_READ_ONLY",
      "summary":{
        "research_jobs_expected":16,"research_jobs_evaluated":len(jobs),
        "unique_parcel_identity_pairs":len(unique_pairs),
        "unique_parcels_queried":len(set(p for p,_ in jobs)),
        "metadata_completed_jobs":completed,
        "still_incomplete_jobs":incomplete,
        "identity_not_found_jobs":not_found,
        "query_error_parcels":len(errors),
        "indeterminate_chronology_jobs_touched":0,
        "database_writes":0
      },
      "query_errors":errors,
      "recheck_results":results,
      "decision_boundary":{
        "targeted_gis_only":True,"chronology_indeterminate_case_untouched":True,
        "database_writes":False,"seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"RECONCILE_COMPLETED_GIS_METADATA_WITH_MEMORY_AND_KEEP_ONLY_TRUE_OPEN_FACTUAL_REMAINDER"
      },
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}
    }
