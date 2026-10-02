#!/usr/bin/env python3
"""V17K — Verification Work Queue / Return Capture Contract. Read-only."""
from operational_verified_evidence_intake_v17j import build_operational_verified_evidence_intake_v17j

VERSION="V17K"
MODE="VERIFICATION_WORK_QUEUE_RETURN_CAPTURE_CONTRACT"

def build_verification_work_queue_v17k():
    src=build_operational_verified_evidence_intake_v17j()
    if src.get("status")!="ok":
        return {"status":"failed","version":VERSION,"error":"V17J prerequisite failed"}

    queue=[]
    for i,r in enumerate(src.get("intake_records") or [],1):
        required=r.get("required_return_fields") or []
        template={"verification_id":r.get("verification_id"),
                  "return_status":None,
                  "source_reference":None}
        for f in required:
            if f not in template:
                template[f]=None
        template["recording_date_source"]=None
        template["verifier_note"]=None

        queue.append({
            "queue_position":i,
            "verification_id":r.get("verification_id"),
            "parcel_id":r.get("parcel_id"),
            "research_request_id":r.get("research_request_id"),
            "unresolved_code":r.get("unresolved_code"),
            "verification_channel":r.get("verification_channel"),
            "work_state":"READY_FOR_MANUAL_VERIFICATION",
            "required_return_fields":required,
            "allowed_return_statuses":r.get("allowed_return_statuses") or [],
            "return_capture_template":template,
            "next_gate":"V17H",
            "persistence_after_validation":"V17I_MODEL",
            "auto_submit":False
        })

    return {
        "status":"ok","version":VERSION,"mode":MODE,
        "market_code":src.get("market_code"),
        "source_contract":{"version":src.get("version"),
                           "awaiting_received":len(queue)},
        "work_queue":queue,
        "queue_summary":{
            "ready_for_manual_verification":len(queue),
            "completed":0,
            "submitted_to_validation":0,
            "persisted":0
        },
        "return_capture_contract":{
            "one_return_per_verification_id":True,
            "explicit_status_required":True,
            "source_reference_required":True,
            "blank_unknown_fields_allowed_only_for_non_verified_status":True,
            "recorddate_source_must_be_explicit":True,
            "original_source_anomaly_must_be_preserved":True,
            "freeform_seller_inference_allowed":False,
            "automatic_submission_allowed":False
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
