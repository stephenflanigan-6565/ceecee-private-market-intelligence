#!/usr/bin/env python3
"""V16X — Read-only analyst brief over proven V16W investigation packets."""
from datetime import datetime, timezone
from operational_investigation_packets_v16w import build_operational_investigation_packets_v16w

VERSION = "V16X"
MODE = "READ_ONLY_INVESTIGATION_ANALYST_BRIEF"
MARKET = "WESTHAMPTON_BEACH_NY"

def _brief(packet):
    pid = str(packet.get("parcel_id"))
    why = packet.get("why_investigate") or {}
    fr = packet.get("factual_research") or {}
    ver = packet.get("verification") or {}
    answers = fr.get("research_answers") or []
    chronology = fr.get("chronology_tail") or []

    facts = []
    for a in answers:
        q = a.get("question")
        if q == "VERIFY_CURRENT_OWNERSHIP_AND_EVENT_CHRONOLOGY":
            facts.append({
                "fact":"CURRENT_SOURCE_AND_TITLE_CONTEXT",
                "latest_event_date":a.get("latest_event_date"),
                "latest_document_code":a.get("latest_document_code"),
                "latest_official_meaning":a.get("latest_official_meaning"),
                "dated_title_events":a.get("dated_title_events"),
                "current_ownership_source_rows":a.get("current_ownership_source_rows"),
                "resolution":a.get("resolution"),
            })
        elif q == "CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_ESTATE_FIDUCIARY_RECORD":
            facts.append({
                "fact":"ORDERED_ESTATE_TO_CONVEYANCE_CHRONOLOGY",
                "prior_event_date":a.get("prior_event_date"),
                "prior_document_code":a.get("prior_document_code"),
                "prior_official_meaning":a.get("prior_official_meaning"),
                "conveyance_date":a.get("conveyance_date"),
                "conveyance_document_code":a.get("conveyance_document_code"),
                "conveyance_official_meaning":a.get("conveyance_official_meaning"),
                "days_between_recorded_events":a.get("days_between_recorded_events"),
                "relationship_scope":a.get("relationship_scope"),
                "resolution":a.get("resolution"),
            })
        elif q == "RECONCILE_MULTIPLE_RECENT_RECORDED_EVENTS":
            facts.append({
                "fact":"RECENT_MULTI_EVENT_CHRONOLOGY",
                "recent_event_count":a.get("recent_event_count"),
                "distinct_event_dates":a.get("distinct_event_dates"),
                "same_day_ordering_present":a.get("same_day_ordering_present"),
                "events":a.get("events") or [],
                "resolution":a.get("resolution"),
            })

    anomalies = []
    for e in chronology:
        d = str(e.get("event_date") or "")
        if d and d[:4].isdigit() and int(d[:4]) < 1800:
            anomalies.append({
                "type":"SOURCE_DATE_REQUIRES_VALIDATION",
                "event_date":d,
                "document_code":e.get("document_code"),
                "treatment":"PRESERVE_SOURCE_VALUE_DO_NOT_SILENTLY_CORRECT"
            })

    next_questions = []
    if ver.get("ownership_verification_gate") != "VERIFIED":
        next_questions.append("MANUALLY_VERIFY_CURRENT_OWNERSHIP_BEFORE_ANY_OWNER_ADDRESSED_CONTACT")
    if "RECENT_CONVEYANCE_WITH_PRIOR_ESTATE_FIDUCIARY" in (why.get("current_event_reasons") or []):
        next_questions.append("VERIFY_RECORDED_PARTIES_AND_INSTRUMENT_RELATIONSHIP_FOR_THE_RECENT_CONVEYANCE")
    if "MULTIPLE_RECORDED_EVENTS_LAST_365D" in (why.get("current_event_reasons") or []):
        next_questions.append("DETERMINE_WHETHER_SAME_DAY_RECENT_RECORDS_ARE_DUPLICATES_OR_DISTINCT_INSTRUMENTS")
    if anomalies:
        next_questions.append("VALIDATE_ANOMALOUS_HISTORICAL_SOURCE_DATE_WITHOUT_ALTERING_SOURCE_HISTORY")

    return {
        "parcel_id":pid,
        "state":packet.get("operational_state"),
        "attention_basis":{
            "current_event_reasons":why.get("current_event_reasons") or [],
            "temporal_state":why.get("temporal_state"),
            "plain_language":"Factual recent title/event context warrants deeper investigation; this is not evidence of seller intent."
        },
        "verified_factual_findings":facts,
        "source_data_quality_flags":anomalies,
        "what_remains_unverified":{
            "ownership_verification_gate":ver.get("ownership_verification_gate"),
            "manual_owner_verification_required_before_contact":ver.get("ownership_verification_gate") != "VERIFIED",
            "seller_intent_known":False,
        },
        "next_factual_research_questions":next_questions,
        "authority_boundary":{
            "investigation_only":True,
            "contact_authorized":False,
            "owner_addressed_outreach_authorized":False,
            "seller_intent_inferred":False,
        }
    }

def build_investigation_analyst_brief_v16x():
    source = build_operational_investigation_packets_v16w()
    if source.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V16W prerequisite failed",
                "guards":{"database_writes":False,"investigate_state_touched":False,
                          "contact_authorized":False,"outreach_touched":False}}
    packets = source.get("investigation_packets") or []
    briefs = [_brief(p) for p in packets]
    return {
        "status":"ok","version":VERSION,"mode":MODE,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "market_code":source.get("market_code", MARKET),
        "source_contract":{
            "version":source.get("version"),
            "packet_count":len(packets),
            "all_source_packets_have_factual_research":
                bool((source.get("packet_summary") or {}).get("all_investigate_records_have_factual_research"))
        },
        "summary":{
            "investigations_presented":len(briefs),
            "contact_ready_count":0,
            "seller_intent_claims":0,
            "data_quality_flags":sum(len(b["source_data_quality_flags"]) for b in briefs),
        },
        "analyst_briefs":briefs,
        "interpretation":[
            "V16X translates proven V16W factual packets into human-readable investigation briefs.",
            "It does not rank properties, create seller scores, infer seller intent, or authorize contact.",
            "Source anomalies are surfaced for validation and are never silently corrected."
        ],
        "guards":{
            "database_writes":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False,
            "owner_names_addresses_emitted":False,
            "sensitive_motivation_inferred":False,
            "price_or_luxury_gate_used":False,
            "source_history_silently_corrected":False,
        }
    }
