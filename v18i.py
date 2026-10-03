#!/usr/bin/env python3
"""V18I — Single Identity Mismatch Resolution.
Read-only. Resolves only parcel 0905010000300004000 / expected TRANSHISSEQ 1225700.
No persistence, promotion, scoring, or modification of the 15 legitimate source-incomplete cases.
"""
import json, urllib.parse, urllib.request

VERSION="V18I"
TARGET_PARCEL="0905010000300004000"
TARGET_ID="1225700"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]

def _canon(v):
    if v is None:return None
    s=str(v).strip()
    return s[:-2] if s.endswith(".0") else s

def _request(where, order=None):
    params={"where":where,"outFields":",".join(FIELDS),"returnGeometry":"false",
            "resultRecordCount":"2000","f":"json"}
    if order: params["orderByFields"]=order
    req=urllib.request.Request(SERVICE+"?"+urllib.parse.urlencode(params),
        headers={"User-Agent":"PrivateMarketIntelligence/18I identity-resolution"})
    with urllib.request.urlopen(req,timeout=30) as r:
        data=json.loads(r.read().decode("utf-8"))
    if data.get("error"):raise RuntimeError(str(data["error"]))
    return [x.get("attributes",{}) for x in data.get("features",[])]

def _clean(a):
    return {k:(_canon(v) if k=="TRANSHISSEQ" else v) for k,v in a.items()}

def build_v18i():
    parcel_rows=_request(f"PARCELID='{TARGET_PARCEL}'","RECORDDATE ASC,TRANSHISSEQ ASC")
    identity_rows=_request(f"TRANSHISSEQ={TARGET_ID}")
    parcel_ids=[_canon(x.get("TRANSHISSEQ")) for x in parcel_rows]
    exact_on_target=[x for x in parcel_rows if _canon(x.get("TRANSHISSEQ"))==TARGET_ID]
    exact_global=[x for x in identity_rows if _canon(x.get("TRANSHISSEQ"))==TARGET_ID]

    if exact_on_target:
        disposition="TARGET_IDENTITY_CONFIRMED_ON_EXPECTED_PARCEL"
        explanation="The expected identity is currently returned by the authoritative source for the expected parcel."
    elif exact_global:
        owners=sorted(set(str(x.get("PARCELID")) for x in exact_global if x.get("PARCELID")))
        disposition="TARGET_IDENTITY_BELONGS_TO_DIFFERENT_PARCEL"
        explanation=f"The authoritative source returns TRANSHISSEQ {TARGET_ID} under parcel(s) {owners}, not the expected parcel."
    else:
        disposition="TARGET_IDENTITY_NOT_PRESENT_IN_CURRENT_AUTHORITATIVE_SOURCE"
        explanation="The expected TRANSHISSEQ is not returned for the expected parcel and is not found by exact authoritative-source identity lookup."

    # Descriptive neighboring identities only; no guess that any one is the replacement.
    numeric=[]
    for x in parcel_rows:
        sid=_canon(x.get("TRANSHISSEQ"))
        try:numeric.append((abs(int(sid)-int(TARGET_ID)),sid,x))
        except:pass
    numeric.sort(key=lambda t:t[0])
    nearest=[{"distance":d,"source_record_id":sid,"record":_clean(x)} for d,sid,x in numeric[:5]]

    return {
      "status":"ok","version":VERSION,"mode":"SINGLE_IDENTITY_MISMATCH_RESOLUTION_READ_ONLY",
      "target":{"parcel_id":TARGET_PARCEL,"expected_source_record_id":TARGET_ID},
      "authoritative_findings":{
        "target_parcel_record_count":len(parcel_rows),
        "target_parcel_source_record_ids":parcel_ids,
        "expected_identity_found_on_target_parcel":bool(exact_on_target),
        "expected_identity_global_match_count":len(exact_global),
        "expected_identity_global_matches":[_clean(x) for x in exact_global],
        "nearest_numeric_identities_on_target_parcel":nearest
      },
      "disposition":disposition,
      "explanation":explanation,
      "decision_boundary":{
        "one_case_only":True,"fifteen_source_incomplete_watch_cases_touched":False,
        "v18g_indeterminate_chronology_case_touched":False,
        "replacement_identity_inferred":False,"database_writes":False,
        "seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"CORRECT_ROUTING_ONLY_IF_AUTHORITATIVE_IDENTITY_OWNERSHIP_IS_FACTUALLY_ESTABLISHED_OTHERWISE_CLOSE_AS_STALE_OR_UNRESOLVED_IDENTITY_REFERENCE"
      },
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}
    }
