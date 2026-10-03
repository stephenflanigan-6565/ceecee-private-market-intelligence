#!/usr/bin/env python3
from delta_specific_research_packets_v17q import build_delta_specific_research_packets_v17q
VERSION="V17R"
MODE="FACTUAL_RESEARCH_QUESTION_MEMORY_VS_FRESH_SOURCE_ROUTING_READ_ONLY"

def build_research_question_source_routing_v17r():
    source=build_delta_specific_research_packets_v17q()
    if source.get("status")!="ok": raise RuntimeError("V17Q prerequisite did not return ok")
    routed=[]
    for p in source.get("research_packets") or []:
        for q in p.get("factual_research_questions") or []:
            question=q.get("question")
            if p.get("packet_type")=="EXISTING_EVENT_REEVALUATION":
                route="EXISTING_MEMORY_REEVALUATION"; fresh=False
                reason="FRESH_AUTHORITATIVE_FIELD_DIFFERENCES_ALREADY_PRESENT_AND_STORED_EVENT_IDENTITY_IS_RESOLVED"
            elif question=="HAS_COUNTY_COMPLETED_RECORDDATE_AND_LIBERPAGE_FOR_NEW_INSTRUMENT":
                route="FRESH_AUTHORITATIVE_GIS_RECHECK"; fresh=True
                reason="CURRENT_PACKET_HAS_NULL_RECORDDATE_AND_LIBERPAGE; ONLY_A_NEW_SOURCE_OBSERVATION_CAN_ESTABLISH_COMPLETION"
            else:
                route="WAIT_FOR_AUTHORITATIVE_METADATA_THEN_REEVALUATE_SEQUENCE"; fresh=True
                reason="PRIOR_TITLE_MEMORY_EXISTS_BUT_NEW_EVENT_LACKS_RECORDDATE; ENTRYDATE_MUST_NOT_SUBSTITUTE_FOR_RECORDDATE"
            routed.append({"parcel_id":p.get("parcel_id"),"source_record_id":p.get("source_record_id"),
              "packet_type":p.get("packet_type"),"question":question,"route":route,
              "fresh_authoritative_source_required":fresh,"reason":reason})
    fresh=sum(1 for x in routed if x["fresh_authoritative_source_required"])
    return {"status":"ok","version":VERSION,"mode":MODE,
      "source_contract":{"version":"V17Q","expected_packet_count":8,"expected_question_count":12},
      "summary":{"questions_routed":len(routed),"answerable_or_reevaluable_from_existing_memory":len(routed)-fresh,
        "fresh_authoritative_source_required":fresh,"properties_represented":len(set(x["parcel_id"] for x in routed))},
      "routes":routed,"protected_counts_before":source.get("protected_counts_before"),
      "protected_counts_after":source.get("protected_counts_after"),
      "protected_state_unchanged":source.get("protected_state_unchanged"),
      "decision_boundary":{"routing_only":True,"external_retrieval_performed":False,"persistence_authorized":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"REEVALUATE_EXISTING_METADATA_COMPLETIONS_AND_PREPARE_TARGETED_GIS_RECHECK_FOR_ONLY_THE_INCOMPLETE_NEW_IDENTITIES"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}
