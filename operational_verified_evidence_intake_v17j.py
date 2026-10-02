#!/usr/bin/env python3
"""V17J — governed operational verified-evidence intake readiness contract. Read-only."""
from manual_verification_packet_v17g import build_manual_verification_packet_v17g

VERSION="V17J"
MODE="OPERATIONAL_VERIFIED_EVIDENCE_INTAKE_READINESS"

def build_operational_verified_evidence_intake_v17j():
    src=build_manual_verification_packet_v17g()
    if src.get("status")!="ok":
        return {"status":"failed","version":VERSION,"error":"V17G prerequisite failed"}
    packets=src.get("verification_packets") or []
    intake=[]
    for p in packets:
        intake.append({
            "verification_id":p.get("verification_id"),
            "parcel_id":p.get("parcel_id"),
            "research_request_id":p.get("research_request_id"),
            "unresolved_code":p.get("unresolved_code"),
            "verification_channel":p.get("verification_channel"),
            "required_return_fields":p.get("required_return_fields") or [],
            "allowed_return_statuses":p.get("return_status_allowed") or [],
            "intake_state":"AWAITING_AUTHORITATIVE_RETURN",
            "persistence_eligible":False,
            "reason":"NO_AUTHORITATIVE_RETURN_SUBMITTED"
        })
    return {
        "status":"ok","version":VERSION,"mode":MODE,
        "market_code":src.get("market_code"),
        "source_contract":{"version":src.get("version"),"packets_received":len(packets)},
        "intake_records":intake,
        "intake_summary":{
            "awaiting_authoritative_return":len(intake),
            "validated_returns":0,
            "persistence_eligible":0,
            "operational_verified_evidence_written":0
        },
        "activation_contract":{
            "required_validation_gate":"V17H",
            "required_persistence_model":"V17I",
            "authoritative_return_required":True,
            "source_reference_required":True,
            "explicit_return_status_required":True,
            "automatic_fact_fabrication_allowed":False,
            "controlled_test_row_operationally_eligible":False
        },
        "guards":{
            "database_writes":False,
            "external_retrieval_performed":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False
        }
    }
