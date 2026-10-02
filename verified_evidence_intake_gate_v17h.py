#!/usr/bin/env python3
"""V17H — Verified Evidence Intake Validation Gate. Validation only; no persistence."""
from manual_verification_packet_v17g import build_manual_verification_packet_v17g

VERSION="V17H"
MODE="VERIFIED_EVIDENCE_INTAKE_VALIDATION_GATE"

def _validate(packet, returned):
    errors=[]
    status=returned.get("return_status")
    allowed=packet.get("return_status_allowed") or []
    if status not in allowed:
        errors.append("INVALID_RETURN_STATUS")
    if not returned.get("source_reference"):
        errors.append("SOURCE_REFERENCE_REQUIRED")
    if status == "VERIFIED":
        for field in packet.get("required_return_fields") or []:
            if field == "authoritative_explanation_if_present":
                continue
            if returned.get(field) in (None, ""):
                errors.append("MISSING_REQUIRED_FIELD:"+field)
    if packet.get("unresolved_code") == "ONE_OR_MORE_TARGET_EVENTS_LACK_RECORDDATE_OR_LIBERPAGE":
        if returned.get("recording_date_source") == "ENTRYDATE":
            errors.append("ENTRYDATE_CANNOT_SUBSTITUTE_FOR_RECORDDATE")
    if packet.get("unresolved_code") == "WHY_SOURCE_DOCUMENT_DATE_FIELD_CONTAINS_1112_11_11":
        if returned.get("observed_document_date") not in (None, "", "1112-11-11"):
            errors.append("ORIGINAL_ANOMALOUS_SOURCE_VALUE_NOT_PRESERVED")
    return {"accepted":not errors,"errors":errors}

def build_verified_evidence_intake_gate_v17h():
    src=build_manual_verification_packet_v17g()
    if src.get("status")!="ok":
        return {"status":"failed","version":VERSION,"error":"V17G prerequisite failed"}
    packets=src.get("verification_packets") or []
    if not packets:
        return {"status":"failed","version":VERSION,"error":"No V17G packets"}

    # Controlled validation cases: prove a complete verified return can pass and
    # malformed/manual evidence is rejected before any persistence authority exists.
    p1=packets[0]
    valid={
        "return_status":"VERIFIED","grantor":"TEST GRANTOR","grantee":"TEST GRANTEE",
        "document_type":"TEST DOCUMENT","recording_date":"2026-01-01",
        "liber_page":"TEST 0001","source_reference":"CONTROLLED_TEST_SOURCE"
    }
    valid_result=_validate(p1,valid)

    invalid_no_source=dict(valid)
    invalid_no_source["source_reference"]=""
    no_source_result=_validate(p1,invalid_no_source)

    invalid_missing=dict(valid)
    invalid_missing["grantor"]=""
    missing_result=_validate(p1,invalid_missing)

    date_packet=next((p for p in packets if p.get("unresolved_code")=="ONE_OR_MORE_TARGET_EVENTS_LACK_RECORDDATE_OR_LIBERPAGE"), None)
    bad_date_result=None
    if date_packet:
        bad_date={
            "return_status":"VERIFIED","recording_date":"2026-09-09",
            "recording_date_source":"ENTRYDATE","liber_page":"TEST",
            "document_type":"TEST","source_reference":"CONTROLLED_TEST_SOURCE"
        }
        bad_date_result=_validate(date_packet,bad_date)

    anomaly_packet=next((p for p in packets if p.get("unresolved_code")=="WHY_SOURCE_DOCUMENT_DATE_FIELD_CONTAINS_1112_11_11"), None)
    anomaly_result=None
    if anomaly_packet:
        changed_anomaly={
            "return_status":"VERIFIED","observed_document_date":"1968-05-20",
            "recording_date":"1968-05-20","liber_page":"06349 0317",
            "source_reference":"CONTROLLED_TEST_SOURCE"
        }
        anomaly_result=_validate(anomaly_packet,changed_anomaly)

    checks={
        "valid_complete_return_accepted":valid_result["accepted"] is True,
        "missing_source_rejected":no_source_result["accepted"] is False and "SOURCE_REFERENCE_REQUIRED" in no_source_result["errors"],
        "missing_required_field_rejected":missing_result["accepted"] is False,
        "entrydate_substitution_rejected":bool(bad_date_result and not bad_date_result["accepted"] and "ENTRYDATE_CANNOT_SUBSTITUTE_FOR_RECORDDATE" in bad_date_result["errors"]),
        "silent_anomaly_correction_rejected":bool(anomaly_result and not anomaly_result["accepted"] and "ORIGINAL_ANOMALOUS_SOURCE_VALUE_NOT_PRESERVED" in anomaly_result["errors"])
    }
    return {
        "status":"ok" if all(checks.values()) else "failed",
        "version":VERSION,"mode":MODE,
        "source_contract":{"version":src.get("version"),"packets_received":len(packets)},
        "validation_checks":checks,
        "controlled_test_results":{
            "valid_complete":valid_result,
            "missing_source":no_source_result,
            "missing_required_field":missing_result,
            "entrydate_substitution":bad_date_result,
            "anomaly_preservation":anomaly_result
        },
        "persistence_authority":False,
        "guards":{
            "database_writes":False,"external_retrieval_performed":False,
            "investigate_state_touched":False,"new_candidate_created":False,
            "seller_intent_inferred":False,"seller_scoring":False,
            "contact_authorized":False,"outreach_touched":False
        }
    }
