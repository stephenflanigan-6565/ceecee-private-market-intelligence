#!/usr/bin/env python3
"""V17U — factual disposition of the eight V17T events. Read-only."""
from v17t import build_v17t

VERSION="V17U"
MODE="EIGHT_EVENT_FACTUAL_DISPOSITION_READ_ONLY"

def build_v17u():
    source=build_v17t()
    if source.get("status") not in ("ok","partial"):
        raise RuntimeError("V17T prerequisite did not return usable status")

    open_new=[]
    for x in source.get("targeted_gis_results") or []:
        open_new.append({
            "parcel_id":x.get("parcel_id"),
            "source_record_id":x.get("source_record_id"),
            "disposition":"OPEN_AUTHORITATIVE_METADATA_COMPLETION",
            "identity_confirmed":bool(x.get("identity_found")),
            "recorddate_present":bool((x.get("authoritative_record") or {}).get("RECORDDATE")),
            "liberpage_present":bool((x.get("authoritative_record") or {}).get("LIBERPAGE")),
            "sequence_interpretation_ready":bool(x.get("sequence_question_ready_for_reevaluation")),
            "open_questions":x.get("questions_waiting") or [],
            "interpretation_limit":"ENTRYDATE_IS_NOT_RECORDDATE; INCOMPLETE_METADATA_DOES_NOT_ESTABLISH_RECORDED_TRANSFER_TIMING"
        })

    existing=[]
    for x in source.get("memory_reevaluation_lane") or []:
        existing.append({
            "parcel_id":x.get("parcel_id"),
            "source_record_id":x.get("source_record_id"),
            "disposition":"SAME_EVENT_AUTHORITATIVE_METADATA_COMPLETION",
            "creates_second_event":False,
            "prior_factual_event_identity_changed":False,
            "factual_interpretation":"AUTHORITATIVE_FIELDS_COMPLETED_FOR_ALREADY_KNOWN_SOURCE_IDENTITY",
            "question_status":"RESOLVED_FROM_EXISTING_MEMORY_AND_ALREADY_RETRIEVED_AUTHORITATIVE_DELTA",
            "seller_intent_conclusion":"NOT_AUTHORIZED"
        })

    return {
      "status":"ok","version":VERSION,"mode":MODE,
      "source_contract":{"version":"V17T","expected_new_incomplete":4,"expected_existing_reevaluations":4},
      "summary":{"events_disposed":len(open_new)+len(existing),
                 "existing_events_resolved":len(existing),
                 "new_events_still_open":len(open_new),
                 "open_questions_remaining":sum(len(x["open_questions"]) for x in open_new),
                 "second_events_created_by_metadata_completion":0},
      "existing_event_dispositions":existing,
      "new_event_open_dispositions":open_new,
      "protected_counts_before":source.get("protected_counts_before"),
      "protected_counts_after":source.get("protected_counts_after"),
      "protected_state_unchanged":source.get("protected_state_unchanged"),
      "decision_boundary":{"factual_disposition_only":True,"persistence_authorized":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"PREPARE_CONTROLLED_MEMORY_UPDATE_FOR_FOUR_RESOLVED_EXISTING_EVENTS_WHILE_KEEPING_FOUR_INCOMPLETE_NEW_EVENTS_OPEN"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}
    }
