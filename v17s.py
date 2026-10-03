#!/usr/bin/env python3
"""V17S — Split V17R into memory re-evaluation and targeted GIS recheck lanes.
Read-only planning/evaluation step. No external retrieval, persistence, or promotion.
"""
from research_question_source_routing_v17r import build_research_question_source_routing_v17r

VERSION="V17S"
MODE="MEMORY_REEVALUATION_AND_TARGETED_GIS_RECHECK_PLAN_READ_ONLY"

def build_v17s():
    source=build_research_question_source_routing_v17r()
    if source.get("status")!="ok":
        raise RuntimeError("V17R prerequisite did not return ok")

    memory=[]
    gis={}
    for r in source.get("routes") or []:
        if r.get("route")=="EXISTING_MEMORY_REEVALUATION":
            memory.append({
                "parcel_id":r.get("parcel_id"),
                "source_record_id":r.get("source_record_id"),
                "question":r.get("question"),
                "evaluation":"AUTHORITATIVE_METADATA_COMPLETION_REQUIRES_REEVALUATION_OF_SAME_STORED_EVENT",
                "creates_second_event":False,
                "fresh_source_required_for_this_question":False
            })
        elif r.get("fresh_authoritative_source_required"):
            key=(r.get("parcel_id"),r.get("source_record_id"))
            job=gis.setdefault(key,{
                "parcel_id":r.get("parcel_id"),
                "source_record_id":r.get("source_record_id"),
                "requested_fields":["RECORDDATE","LIBERPAGE","DOCDATE","ENTRYDATE","DOCCODE","DOCNUM","TRANSHISSEQ"],
                "purpose":"CHECK_AUTHORITATIVE_COMPLETION_FOR_EXISTING_NEW_SOURCE_IDENTITY",
                "questions_waiting":[]
            })
            job["questions_waiting"].append(r.get("question"))

    jobs=list(gis.values())
    return {
        "status":"ok","version":VERSION,"mode":MODE,
        "source_contract":{"version":"V17R","expected_question_count":12},
        "summary":{
            "memory_reevaluations":len(memory),
            "targeted_gis_recheck_jobs":len(jobs),
            "questions_waiting_on_gis":sum(len(x["questions_waiting"]) for x in jobs),
            "properties_represented":len(set([x["parcel_id"] for x in memory]+[x["parcel_id"] for x in jobs]))
        },
        "memory_reevaluation_lane":memory,
        "targeted_gis_recheck_lane":jobs,
        "protected_counts_before":source.get("protected_counts_before"),
        "protected_counts_after":source.get("protected_counts_after"),
        "protected_state_unchanged":source.get("protected_state_unchanged"),
        "decision_boundary":{
            "external_retrieval_performed":False,
            "gis_jobs_prepared_only":True,
            "persistence_authorized":False,
            "investigate_promotion_authorized":False,
            "next_step_if_clean":"RUN_TARGETED_GIS_RECHECK_FOR_FOUR_SOURCE_IDENTITIES_AND_COMBINE_WITH_FOUR_MEMORY_REEVALUATIONS"
        },
        "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
                  "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
                  "outreach_touched":False,"clerk_kiosk_scraped":False}
    }
