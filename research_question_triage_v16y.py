#!/usr/bin/env python3
"""V16Y — Read-only research question triage over proven V16X analyst briefs.

Purpose: turn each open factual question into an explicit resolution route:
- INTERNAL_EVIDENCE_REVIEW
- SOURCE_DETAIL_ENRICHMENT_REQUIRED
- MANUAL_VERIFICATION_REQUIRED
No question is declared resolved unless the current evidence supports it.
"""
from datetime import datetime, timezone
from investigation_analyst_brief_v16x import build_investigation_analyst_brief_v16x

VERSION = "V16Y"
MODE = "READ_ONLY_RESEARCH_QUESTION_TRIAGE"
MARKET = "WESTHAMPTON_BEACH_NY"

def _route_question(q, brief):
    findings = brief.get("verified_factual_findings") or []
    flags = brief.get("source_data_quality_flags") or []
    gate = (brief.get("what_remains_unverified") or {}).get("ownership_verification_gate")

    if q == "MANUALLY_VERIFY_CURRENT_OWNERSHIP_BEFORE_ANY_OWNER_ADDRESSED_CONTACT":
        return {
            "question": q,
            "resolution_state": "UNRESOLVED",
            "resolution_route": "MANUAL_VERIFICATION_REQUIRED",
            "reason": "Current ownership evidence remains below VERIFIED at the Ownership Verification Gate.",
            "current_gate": gate,
            "can_machine_close_now": False,
        }

    if q == "VERIFY_RECORDED_PARTIES_AND_INSTRUMENT_RELATIONSHIP_FOR_THE_RECENT_CONVEYANCE":
        chronology = [x for x in findings if x.get("fact") == "ORDERED_ESTATE_TO_CONVEYANCE_CHRONOLOGY"]
        return {
            "question": q,
            "resolution_state": "PARTIALLY_RESOLVED",
            "resolution_route": "SOURCE_DETAIL_ENRICHMENT_REQUIRED",
            "reason": "PMI has confirmed recorded chronology and instrument types, but current packet does not contain recorded-party identities or instrument-level relationship detail.",
            "existing_chronology": chronology,
            "can_machine_close_now": False,
        }

    if q == "DETERMINE_WHETHER_SAME_DAY_RECENT_RECORDS_ARE_DUPLICATES_OR_DISTINCT_INSTRUMENTS":
        multi = [x for x in findings if x.get("fact") == "RECENT_MULTI_EVENT_CHRONOLOGY"]
        return {
            "question": q,
            "resolution_state": "UNRESOLVED",
            "resolution_route": "SOURCE_DETAIL_ENRICHMENT_REQUIRED",
            "reason": "The current evidence proves two same-day recorded events but lacks instrument identifiers sufficient to distinguish duplicate source rows from distinct instruments.",
            "existing_multi_event_context": multi,
            "can_machine_close_now": False,
        }

    if q == "VALIDATE_ANOMALOUS_HISTORICAL_SOURCE_DATE_WITHOUT_ALTERING_SOURCE_HISTORY":
        return {
            "question": q,
            "resolution_state": "UNRESOLVED_DATA_QUALITY",
            "resolution_route": "SOURCE_DETAIL_ENRICHMENT_REQUIRED",
            "reason": "The anomalous date is preserved exactly as supplied. Validation requires authoritative source detail; PMI must not silently repair it.",
            "existing_flags": flags,
            "can_machine_close_now": False,
        }

    return {
        "question": q,
        "resolution_state": "UNRESOLVED",
        "resolution_route": "INTERNAL_EVIDENCE_REVIEW",
        "reason": "No specialized resolution rule exists yet; retain as an open factual research question.",
        "can_machine_close_now": False,
    }

def build_research_question_triage_v16y():
    source = build_investigation_analyst_brief_v16x()
    if source.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V16X prerequisite failed",
                "guards":{"database_writes":False,"investigate_state_touched":False,
                          "contact_authorized":False,"outreach_touched":False}}

    briefs = source.get("analyst_briefs") or []
    work = []
    counts = {}
    total = 0
    for brief in briefs:
        routed = [_route_question(q, brief) for q in (brief.get("next_factual_research_questions") or [])]
        for r in routed:
            total += 1
            k = r["resolution_route"]
            counts[k] = counts.get(k, 0) + 1
        work.append({
            "parcel_id": brief.get("parcel_id"),
            "state": brief.get("state"),
            "open_question_count": len(routed),
            "research_work_items": routed,
            "authority_boundary": {
                "investigation_only": True,
                "contact_authorized": False,
                "seller_intent_inferred": False,
            }
        })

    return {
        "status":"ok","version":VERSION,"mode":MODE,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "market_code":source.get("market_code", MARKET),
        "source_contract":{
            "version":source.get("version"),
            "investigations_presented":len(briefs),
        },
        "summary":{
            "investigations_triaged":len(work),
            "open_questions_triaged":total,
            "resolution_route_counts":counts,
            "questions_machine_closed_without_new_evidence":0,
        },
        "research_queue":work,
        "interpretation":[
            "V16Y converts V16X open questions into explicit research routes without inventing answers.",
            "Known chronology is reused; missing instrument/party detail remains unresolved until better evidence exists.",
            "Manual ownership verification remains separate from machine research and contact authority."
        ],
        "guards":{
            "database_writes":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "question_falsely_marked_resolved":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False,
            "owner_names_addresses_emitted":False,
            "source_history_silently_corrected":False,
        }
    }
