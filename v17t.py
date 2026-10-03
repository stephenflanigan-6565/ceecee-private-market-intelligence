#!/usr/bin/env python3
"""V17T — targeted Suffolk GIS recheck for the four V17S identities + memory lane merge.
Read-only. No persistence or state promotion.
"""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from v17s import build_v17s

VERSION="V17T"
MODE="TARGETED_GIS_RECHECK_AND_MEMORY_REEVALUATION_READ_ONLY"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

def _fetch(parcel_id):
    params={"where":"PARCELID='{}'".format(parcel_id.replace("'","''")),
            "outFields":",".join(FIELDS),"returnGeometry":"false",
            "orderByFields":"RECORDDATE ASC,TRANSHISSEQ ASC","resultRecordCount":"2000","f":"json"}
    req=Request(SERVICE+"?"+urlencode(params),headers={"User-Agent":"PrivateMarketIntelligence/17T factual-research"})
    with urlopen(req,timeout=30) as r:
        data=json.loads(r.read().decode("utf-8"))
    if data.get("error"): raise RuntimeError(str(data["error"]))
    return [x.get("attributes") or {} for x in data.get("features") or []]

def _sid(v):
    if v is None: return None
    s=str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit(): return s[:-2]
    return s

def _date(v):
    if v is None: return None
    if isinstance(v,(int,float)):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(v/1000,tz=timezone.utc).date().isoformat()
    return str(v)

def build_v17t():
    source=build_v17s()
    if source.get("status")!="ok": raise RuntimeError("V17S prerequisite did not return ok")

    fresh=[]
    errors=[]
    for job in source.get("targeted_gis_recheck_lane") or []:
        try:
            rows=_fetch(job["parcel_id"])
            target=next((r for r in rows if _sid(r.get("TRANSHISSEQ"))==_sid(job["source_record_id"])),None)
            if target:
                normalized={k:(_date(target.get(k)) if k in ("RECORDDATE","DOCDATE","ENTRYDATE") else target.get(k)) for k in FIELDS}
                complete=bool(normalized.get("RECORDDATE") and normalized.get("LIBERPAGE"))
                fresh.append({"parcel_id":job["parcel_id"],"source_record_id":job["source_record_id"],
                    "identity_found":True,"recording_metadata_complete":complete,
                    "authoritative_record":normalized,
                    "sequence_question_ready_for_reevaluation":complete,
                    "questions_waiting":job.get("questions_waiting")})
            else:
                fresh.append({"parcel_id":job["parcel_id"],"source_record_id":job["source_record_id"],
                    "identity_found":False,"recording_metadata_complete":False,
                    "authoritative_record":None,"sequence_question_ready_for_reevaluation":False,
                    "questions_waiting":job.get("questions_waiting")})
        except Exception as e:
            errors.append({"parcel_id":job["parcel_id"],"source_record_id":job["source_record_id"],
                           "error_type":type(e).__name__,"error":str(e)[:500]})

    complete=sum(1 for x in fresh if x["recording_metadata_complete"])
    return {"status":"ok" if not errors else "partial","version":VERSION,"mode":MODE,
      "source_contract":{"version":"V17S","expected_targeted_gis_jobs":4,"expected_memory_reevaluations":4},
      "summary":{"targeted_gis_jobs_attempted":4,"target_identities_returned":len(fresh),
                 "recording_metadata_now_complete":complete,
                 "recording_metadata_still_incomplete":len(fresh)-complete,
                 "memory_reevaluations_carried_forward":len(source.get("memory_reevaluation_lane") or []),
                 "query_errors":len(errors)},
      "targeted_gis_results":fresh,
      "memory_reevaluation_lane":source.get("memory_reevaluation_lane"),
      "query_errors":errors,
      "protected_counts_before":source.get("protected_counts_before"),
      "protected_counts_after":source.get("protected_counts_after"),
      "protected_state_unchanged":source.get("protected_state_unchanged"),
      "decision_boundary":{"targeted_external_retrieval_performed":True,"full_universe_refresh":False,
        "persistence_authorized":False,"investigate_promotion_authorized":False,
        "next_step_if_clean":"RESOLVE_WHAT_CHANGED_FACTUALLY_FOR_EIGHT_EVENTS_AND_DECIDE_WHICH_QUESTIONS_REMAIN_OPEN"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}
