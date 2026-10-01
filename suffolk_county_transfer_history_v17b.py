#!/usr/bin/env python3
"""V17B — Suffolk County GIS Transfer History targeted retrieval.

Performs bounded read-only retrieval from Suffolk County's public ArcGIS REST
TaxParcelTransferHistory table for the V17A parcel jobs. It accepts only the
published transfer-history schema and never treats absent party fields as known.
"""
from datetime import datetime, timezone
import json
import urllib.parse
import urllib.request
from suffolk_clerk_retrieval_adapter_v17a import build_suffolk_clerk_retrieval_adapter_contract_v17a

VERSION = "V17B"
MODE = "READ_ONLY_SUFFOLK_COUNTY_GIS_TRANSFER_HISTORY_RETRIEVAL"
SERVICE = "https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
EXPECTED_FIELDS = ["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

def _arc_date(ms):
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(float(ms)/1000.0, tz=timezone.utc).date().isoformat()
    except Exception:
        return None

def _fetch(parcel_id):
    params = {
        "where": "PARCELID='{}'".format(parcel_id.replace("'","''")),
        "outFields": ",".join(EXPECTED_FIELDS),
        "returnGeometry": "false",
        "orderByFields": "RECORDDATE ASC,TRANSHISSEQ ASC",
        "resultRecordCount": "2000",
        "f": "json",
    }
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent":"PrivateMarketIntelligence/17B factual-research"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError("County GIS query error: " + str(payload["error"])[:300])
    records = []
    for f in payload.get("features") or []:
        a = f.get("attributes") or {}
        if str(a.get("PARCELID") or "") != parcel_id:
            continue
        records.append({
            "parcel_id":a.get("PARCELID"),
            "liber_page":a.get("LIBERPAGE"),
            "record_date":_arc_date(a.get("RECORDDATE")),
            "document_number":a.get("DOCNUM"),
            "document_code":a.get("DOCCODE"),
            "document_date":_arc_date(a.get("DOCDATE")),
            "entry_date":_arc_date(a.get("ENTRYDATE")),
            "history_sequence":a.get("TRANSHISSEQ"),
            "source":"SUFFOLK_COUNTY_GIS_TAXPARCELTRANSFERHISTORY",
        })
    return url, records

def _match_job(job, records):
    window = job.get("search_window") or {}
    start, end = window.get("date_from"), window.get("date_to")
    target = job.get("evidence_target")
    relevant = [r for r in records if (not start or (r["record_date"] and r["record_date"] >= start))
                                      and (not end or (r["record_date"] and r["record_date"] <= end))]
    result = {
        "research_request_id":job.get("research_request_id"),
        "parcel_id":job.get("parcel_id"),
        "evidence_target":target,
        "county_records_in_window":relevant,
        "resolution_state":"PARTIAL_AUTHORITATIVE_EVIDENCE",
        "resolved_facts":[],
        "remaining_unknowns":[],
    }
    if target == "SAME_DAY_INSTRUMENT_IDENTITY":
        ids = {(r.get("liber_page"),r.get("document_number")) for r in relevant
               if r.get("document_code") == "WRD"}
        if len(ids) >= 2:
            result["resolution_state"] = "DISTINCT_AUTHORITATIVE_INSTRUMENT_IDENTITIES"
            result["resolved_facts"].append("SAME_DAY_WRD_RECORDS_HAVE_DISTINCT_COUNTY_DOCUMENT_IDENTITIES")
        elif len(ids) == 1 and len([r for r in relevant if r.get("document_code")=="WRD"]) >= 2:
            result["resolution_state"] = "SAME_AUTHORITATIVE_IDENTITY_REPEATED"
            result["resolved_facts"].append("SAME_DAY_WRD_ROWS_REPEAT_THE_SAME_COUNTY_DOCUMENT_IDENTITY")
        else:
            result["resolution_state"] = "UNRESOLVED_INSUFFICIENT_MATCHING_RECORDS"
    elif target == "RECORDED_INSTRUMENT_DETAIL":
        result["resolved_facts"].append("COUNTY_INSTRUMENT_IDENTITY_AND_RECORDING_METADATA_AVAILABLE")
        result["remaining_unknowns"].append("RECORDED_PARTY_ROLES_NOT_EXPOSED_BY_THIS_GIS_TABLE")
    elif target == "HISTORICAL_RECORD_DATE_VALIDATION":
        result["resolution_state"] = "UNRESOLVED_BY_THIS_ONLINE_TRANSFER_HISTORY_QUERY"
        result["remaining_unknowns"].append("ANOMALOUS_HISTORICAL_SOURCE_DATE_REQUIRES_SEPARATE_AUTHORITATIVE_VALIDATION")
    return result

def build_suffolk_county_transfer_history_retrieval_v17b():
    source = build_suffolk_clerk_retrieval_adapter_contract_v17a()
    if source.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V17A prerequisite failed"}
    # Query each unique parcel once; reuse results across its research questions.
    jobs = source.get("retrieval_jobs") or []
    parcel_cache, provenance = {}, {}
    errors = {}
    for pid in sorted({str(j.get("parcel_id")) for j in jobs}):
        try:
            url, recs = _fetch(pid)
            parcel_cache[pid] = recs
            provenance[pid] = {"service":SERVICE,"query_url":url,"retrieved_at":datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            parcel_cache[pid] = []
            errors[pid] = {"error_type":type(e).__name__,"error":str(e)[:300]}
    results = [_match_job(j, parcel_cache.get(str(j.get("parcel_id")), [])) for j in jobs]
    return {
        "status":"ok" if not errors else "partial",
        "version":VERSION,"mode":MODE,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "market_code":source.get("market_code"),
        "source_contract":{"version":source.get("version"),"retrieval_jobs_received":len(jobs)},
        "county_service_contract":{
            "service":"TaxParcelTransferHistory",
            "published_fields":EXPECTED_FIELDS,
            "party_fields_exposed":False,
            "read_only":True,
        },
        "summary":{
            "unique_parcels_queried":len(parcel_cache),
            "research_questions_evaluated":len(results),
            "county_records_retrieved":sum(len(v) for v in parcel_cache.values()),
            "query_errors":len(errors),
            "database_writes":0,
        },
        "research_results":results,
        "source_provenance":provenance,
        "query_errors":errors,
        "guards":{
            "database_writes":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "clerk_kiosk_scraped":False,
            "paid_document_purchase_performed":False,
            "grantor_grantee_claimed_from_gis":False,
            "manual_ownership_verification_bypassed":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False,
            "source_history_silently_corrected":False,
        }
    }
