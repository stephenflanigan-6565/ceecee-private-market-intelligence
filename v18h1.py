#!/usr/bin/env python3
"""V18H1 — Corrected Targeted Authoritative GIS Recheck.
Read-only. Preserves the exact 16 V18F GIS research jobs and their parcel/identity sets.
"""
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
import psycopg

VERSION="V18H1"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

JOBS=[
("0905003000100010000",["2140200186911"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905003000100028000",["2140200186973"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905006000100026000",["1242908","2140200188450","2140200188451"],"RECENT_TRANSFER_SEQUENCE",["RECENT_RECORDING_IDENTITY_OR_RECORDDATE","LIBERPAGE"]),
("0905006000100026000",["1242908","2140200188451"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905006000200009000",["2140200188523"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905007000200024000",["1000289","1239577","2140200189072","3924"],"RECENT_TRANSFER_SEQUENCE",["RECENT_RECORDING_IDENTITY_OR_RECORDDATE","LIBERPAGE"]),
("0905015000200016000",["1227412","1239971","313832","51632"],"RECENT_TRANSFER_SEQUENCE",["RECENT_RECORDING_IDENTITY_OR_RECORDDATE","LIBERPAGE"]),
("0905015000200016000",["1227412","1239971"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905015000300011000",["2140200193495"],"RARE_DOCUMENT_DETAIL",["RECORDDATE","LIBERPAGE"]),
("0905008000100014002",["2140200189245"],"RARE_DOCUMENT_DETAIL",["RECORDDATE","LIBERPAGE"]),
("0905008000200015002",["434354","434357"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905009000100020000",["1226308","1238113","2140200189680","2140200189681","2140200189682","2140200189683","2140200189684","2140200189685","2140200189686","2140200189687"],"RECENT_TRANSFER_SEQUENCE",["RECENT_RECORDING_IDENTITY_OR_RECORDDATE","LIBERPAGE"]),
("0905009000100023000",["1228516"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905009000200026002",["1242252"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905010000300004000",["1225700"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
("0905017000300028000",["2140200194331"],"NON_BSD_CHRONOLOGY",["RECORDDATE","LIBERPAGE"]),
]

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")
def _canon(v):
    if v is None:return None
    s=str(v).strip()
    return s[:-2] if s.endswith(".0") else s
def _iso(v):
    if v in (None,""):return None
    try:
        if isinstance(v,(int,float)) or str(v).strip().lstrip("-").isdigit():
            return datetime.fromtimestamp(int(float(v))/1000,tz=timezone.utc).date().isoformat()
        return str(v)[:10]
    except:return str(v)[:10]
def _fetch(parcel):
    params={"where":f"PARCELID='{parcel}'","outFields":",".join(FIELDS),"returnGeometry":"false",
            "orderByFields":"RECORDDATE ASC,TRANSHISSEQ ASC","resultRecordCount":"2000","f":"json"}
    req=urllib.request.Request(SERVICE+"?"+urllib.parse.urlencode(params),
        headers={"User-Agent":"PrivateMarketIntelligence/18H1 factual-research"})
    with urllib.request.urlopen(req,timeout=30) as r:data=json.loads(r.read().decode())
    if data.get("error"):raise RuntimeError(str(data["error"]))
    return [x.get("attributes",{}) for x in data.get("features",[])]

def build_v18h1():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,source_record_id FROM evidence_ledger
                       WHERE is_current=1 AND evidence_family='TRANSFER_TITLE'""")
        stored={(r[0],_canon(r[1])) for r in cur.fetchall()}

    cache={}; errors={}
    for parcel,_,_,_ in JOBS:
        if parcel in cache or parcel in errors:continue
        try:cache[parcel]=_fetch(parcel)
        except Exception as e:errors[parcel]=f"{type(e).__name__}: {str(e)[:500]}"

    results=[]; job_states={}
    for idx,(parcel,ids,qtype,expected_missing) in enumerate(JOBS,1):
        fmap={_canon(a.get("TRANSHISSEQ")):a for a in cache.get(parcel,[])}
        id_results=[]
        for sid in ids:
            a=fmap.get(_canon(sid))
            missing=[]
            if not a: missing=["IDENTITY"]
            else:
                if not _iso(a.get("RECORDDATE")):missing.append("RECORDDATE")
                if not a.get("LIBERPAGE"):missing.append("LIBERPAGE")
            id_results.append({
              "source_record_id":sid,"identity_found":bool(a),
              "stored_identity_present":(parcel,sid) in stored,
              "missing_after_recheck":missing,
              "fresh_authoritative":{
                "DOCCODE":a.get("DOCCODE") if a else None,
                "DOCDATE":_iso(a.get("DOCDATE")) if a else None,
                "ENTRYDATE":_iso(a.get("ENTRYDATE")) if a else None,
                "LIBERPAGE":a.get("LIBERPAGE") if a else None,
                "RECORDDATE":_iso(a.get("RECORDDATE")) if a else None,
                "TRANSHISSEQ":_canon(a.get("TRANSHISSEQ")) if a else None}})
        if parcel in errors: state="QUERY_ERROR"
        elif any(not x["identity_found"] for x in id_results):state="IDENTITY_NOT_FOUND"
        elif any(x["missing_after_recheck"] for x in id_results):state="STILL_INCOMPLETE"
        else:state="METADATA_COMPLETED"
        job_states[state]=job_states.get(state,0)+1
        results.append({"job_number":idx,"parcel_id":parcel,"question_type":qtype,
          "target_source_record_ids":ids,"expected_missing_evidence":expected_missing,
          "recheck_state":state,"identity_results":id_results,
          "source_semantics":"ENTRYDATE is county system entry/presence date only and is never substituted for RECORDDATE."})

    return {"status":"ok","version":VERSION,"mode":"CORRECTED_TARGETED_AUTHORITATIVE_GIS_RECHECK_READ_ONLY",
      "summary":{"research_jobs_expected":16,"research_jobs_evaluated":len(results),
        "unique_parcels_queried":len(set(x[0] for x in JOBS)),
        "unique_parcel_identity_pairs":len(set((p,i) for p,ids,_,_ in JOBS for i in ids)),
        "job_state_counts":job_states,"query_error_parcels":len(errors),
        "indeterminate_chronology_jobs_touched":0,"database_writes":0},
      "query_errors":errors,"recheck_results":results,
      "decision_boundary":{"corrected_v18f_mapping_preserved":True,"targeted_gis_only":True,
        "chronology_indeterminate_case_untouched":True,"database_writes":False,
        "seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"RECONCILE_ONLY_FACTUALLY_COMPLETED_METADATA_AND_KEEP_TRUE_OPEN_REMAINDER"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
