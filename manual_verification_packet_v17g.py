#!/usr/bin/env python3
"""V17G — Manual Verification Packet / Evidence Return Contract. Read-only."""
from unresolved_research_router_v17f import build_unresolved_research_router_v17f

VERSION = "V17G"
MODE = "MANUAL_VERIFICATION_PACKET_EVIDENCE_RETURN_CONTRACT_READ_ONLY"

def _required_fields(job):
    code = job.get("unresolved_code")
    if code == "RECORDED_PARTY_ROLES_NOT_EXPOSED_BY_GIS":
        return ["grantor", "grantee", "document_type", "recording_date", "liber_page", "source_reference"]
    if code == "ONE_OR_MORE_TARGET_EVENTS_LACK_RECORDDATE_OR_LIBERPAGE":
        return ["recording_date", "liber_page", "document_type", "source_reference"]
    if code == "WHY_SOURCE_DOCUMENT_DATE_FIELD_CONTAINS_1112_11_11":
        return ["observed_document_date", "recording_date", "liber_page", "source_reference", "authoritative_explanation_if_present"]
    return ["source_reference", "verified_fact"]

def build_manual_verification_packet_v17g():
    src = build_unresolved_research_router_v17f()
    if src.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V17F prerequisite failed"}

    jobs = src.get("research_jobs") or []
    packets = []
    for job in jobs:
        packets.append({
            "verification_id": "V17G:" + str(job.get("job_id")),
            "job_id": job.get("job_id"),
            "parcel_id": job.get("parcel_id"),
            "research_request_id": job.get("research_request_id"),
            "unresolved_code": job.get("unresolved_code"),
            "verification_channel": job.get("resolution_channel"),
            "research_action": job.get("research_action"),
            "required_return_fields": _required_fields(job),
            "return_status_allowed": ["VERIFIED", "NOT_FOUND", "CONFLICT", "SOURCE_UNAVAILABLE"],
            "source_value_preservation_required": True,
            "freeform_inference_allowed": False
        })

    return {
        "status":"ok",
        "version":VERSION,
        "mode":MODE,
        "market_code":src.get("market_code"),
        "source_contract":{
            "version":src.get("version"),
            "jobs_received":len(jobs)
        },
        "verification_packets":packets,
        "packet_summary":{
            "packets_prepared":len(packets),
            "manual_verification_packets":sum(1 for p in packets if p["verification_channel"] in
                ("SUFFOLK_COUNTY_CLERK_MANUAL_VERIFICATION","SOURCE_RECORD_VALIDATION")),
            "machine_closed_without_new_evidence":0
        },
        "evidence_return_contract":{
            "append_verified_evidence_only":True,
            "preserve_original_source_values":True,
            "do_not_replace_recorddate_with_entrydate":True,
            "do_not_silently_correct_anomalies":True,
            "require_source_reference":True,
            "require_explicit_return_status":True,
            "allowed_return_statuses":["VERIFIED","NOT_FOUND","CONFLICT","SOURCE_UNAVAILABLE"],
            "seller_intent_fields_allowed":False,
            "contact_authority_fields_allowed":False
        },
        "guards":{
            "database_writes":False,
            "external_retrieval_performed":False,
            "clerk_site_scraped":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False
        }
    }
