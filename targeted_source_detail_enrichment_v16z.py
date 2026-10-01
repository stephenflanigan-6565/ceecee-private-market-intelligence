#!/usr/bin/env python3
"""V16Z — Targeted Source Detail Enrichment Plan."""
from datetime import datetime, timezone
from research_question_triage_v16y import build_research_question_triage_v16y

VERSION = "V16Z"
MODE = "READ_ONLY_TARGETED_SOURCE_DETAIL_ENRICHMENT_PLAN"
MARKET = "WESTHAMPTON_BEACH_NY"

def _requirements(question, item):
    if question == "VERIFY_RECORDED_PARTIES_AND_INSTRUMENT_RELATIONSHIP_FOR_THE_RECENT_CONVEYANCE":
        return {
            "authoritative_evidence_target":"RECORDED_INSTRUMENT_DETAIL",
            "required_fields":["parcel_id","recording_date","document_code","instrument_or_document_id",
                               "recorded_party_names_or_roles","grantor_grantee_or_equivalent_roles",
                               "book_page_or_recording_reference_if_available"],
            "target_events":item.get("existing_chronology") or [],
            "resolution_test":"Match the relevant estate/fiduciary and conveyance instruments to authoritative recording identifiers and recorded-party roles; describe only the documented relationship."
        }
    if question == "DETERMINE_WHETHER_SAME_DAY_RECENT_RECORDS_ARE_DUPLICATES_OR_DISTINCT_INSTRUMENTS":
        return {
            "authoritative_evidence_target":"SAME_DAY_INSTRUMENT_IDENTITY",
            "required_fields":["parcel_id","recording_date","document_code","instrument_or_document_id",
                               "book_page_or_recording_reference_if_available","recorded_party_roles"],
            "target_events":item.get("existing_multi_event_context") or [],
            "resolution_test":"Compare authoritative instrument identifiers/recording references for the two same-day records. Identical identity may support duplicate-source classification; distinct identity supports separate recorded instruments."
        }
    if question == "VALIDATE_ANOMALOUS_HISTORICAL_SOURCE_DATE_WITHOUT_ALTERING_SOURCE_HISTORY":
        return {
            "authoritative_evidence_target":"HISTORICAL_RECORD_DATE_VALIDATION",
            "required_fields":["parcel_id","source_record_identity","authoritative_recording_date",
                               "document_code_if_available","recording_reference_if_available"],
            "target_events":item.get("existing_flags") or [],
            "resolution_test":"Compare the preserved anomalous source date with authoritative record detail. Classify the source value as validated, contradicted, or unresolved; never overwrite it."
        }
    return {
        "authoritative_evidence_target":"UNCLASSIFIED_SOURCE_DETAIL",
        "required_fields":["parcel_id","authoritative_source_reference"],
        "target_events":[],
        "resolution_test":"Acquire authoritative evidence sufficient to answer the factual question without inference."
    }

def build_targeted_source_detail_enrichment_plan_v16z():
    source = build_research_question_triage_v16y()
    if source.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V16Y prerequisite failed",
                "guards":{"database_writes":False,"contact_authorized":False,
                          "seller_intent_inferred":False,"external_retrieval_performed":False}}
    requests = []
    for parcel in source.get("research_queue") or []:
        pid = str(parcel.get("parcel_id"))
        for item in parcel.get("research_work_items") or []:
            if item.get("resolution_route") != "SOURCE_DETAIL_ENRICHMENT_REQUIRED":
                continue
            q = item.get("question")
            requests.append({
                "research_request_id":f"{VERSION}:{pid}:{q}",
                "parcel_id":pid,
                "question":q,
                "current_resolution_state":item.get("resolution_state"),
                "why_more_evidence_is_needed":item.get("reason"),
                **_requirements(q, item),
                "research_authority":"FACTUAL_INVESTIGATION_ONLY",
                "contact_authorized":False,
                "seller_intent_inferred":False
            })
    return {
        "status":"ok","version":VERSION,"mode":MODE,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "market_code":source.get("market_code", MARKET),
        "source_contract":{
            "version":source.get("version"),
            "open_questions_triaged":(source.get("summary") or {}).get("open_questions_triaged"),
            "expected_source_detail_requests":(source.get("summary") or {}).get("resolution_route_counts",{}).get("SOURCE_DETAIL_ENRICHMENT_REQUIRED")
        },
        "summary":{
            "targeted_source_detail_requests":len(requests),
            "properties_requiring_source_detail":len({r["parcel_id"] for r in requests}),
            "external_retrieval_performed":False,
            "questions_declared_resolved":0
        },
        "enrichment_requests":requests,
        "next_stage_contract":{
            "name":"AUTHORITATIVE_SOURCE_RETRIEVAL_ADAPTER",
            "input":"V16Z enrichment_requests",
            "required_behavior":["retrieve only requested factual source detail",
                                 "retain source provenance and authoritative reference",
                                 "never infer seller motivation or vulnerability",
                                 "never authorize contact",
                                 "never silently repair historical source values",
                                 "return unresolved when evidence is insufficient"]
        },
        "interpretation":[
            "V16Z is the controlled handoff from detected knowledge gaps to targeted authoritative-source research.",
            "It performs no external retrieval in this version and therefore resolves no question by itself.",
            "Only SOURCE_DETAIL_ENRICHMENT_REQUIRED work from V16Y is emitted; manual ownership verification stays separate."
        ],
        "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
                  "external_retrieval_performed":False,"question_falsely_marked_resolved":False,
                  "manual_ownership_verification_bypassed":False,"seller_intent_inferred":False,
                  "seller_scoring":False,"contact_authorized":False,"outreach_touched":False,
                  "source_history_silently_corrected":False}
    }
