#!/usr/bin/env python3
from datetime import datetime, timezone
from collections import Counter
from property_research_router_v1 import build_property_research_router_v1

VERSION="ASSESSMENT_IMPROVEMENT_FACT_RESOLUTION_V1"
TARGET_ROUTE="VERIFY_IMPROVEMENT_AND_ASSESSMENT_SEMANTICS"


def _resolve(c):
    # The source-semantics audit established these consumption rules population-wide.
    quality=list(c.get("data_quality_uncertainties") or [])
    quality=[q for q in quality if q != "MARKET_VALUE_FIELD_SEMANTICS_UNRESOLVED"]
    removed=["FULL_MARKET_VALUE_ZERO_POPULATION_WIDE_NOT_OPPORTUNITY_EVIDENCE"]
    if "ZERO_FULL_BATHS_PLAUSIBILITY_CHECK" in quality:
        removed.append("ZERO_FULL_BATHS_IS_PLAUSIBILITY_WARNING_NOT_OPPORTUNITY_EVIDENCE")

    # This experiment does not invent new facts. It resolves what can be concluded from
    # the audited semantics and names the next material fact when existing rails cannot.
    return {
      "parcel_id":c.get("parcel_id"),
      "property_address":c.get("property_address"),
      "property_class":c.get("property_class"),
      "source_disposition":c.get("current_disposition"),
      "source_research_route":c.get("research_route"),
      "resolution_state":"ASSESSMENT_COMPONENTS_CONFIRMED_SEMANTICALLY_BUT_PROPERTY_CAUSE_UNRESOLVED",
      "why_pmi_found_it":"LAND_VERSUS_IMPROVEMENT_ASSESSMENT_RELATIONSHIP_REMAINED_UNUSUAL_AFTER_PHYSICAL_PEER_EXPLANATION",
      "verified_consumable_evidence":[
        "ASSESSED_TOTAL_IS_USABLE_AS_ASSESSMENT_COMPONENT",
        "ASSESSED_LAND_IS_USABLE_AS_ASSESSMENT_COMPONENT",
        "IMPROVEMENT_ASSESSMENT_MAY_BE_DERIVED_AS_ASSESSED_TOTAL_MINUS_ASSESSED_LAND_WHEN_TOTAL_GTE_LAND",
        "PROPERTY_CLASS_MAY_BE_USED_AS_PEER_GROUPING_KEY_WITHOUT_ASSERTING_CLASS_CODE_MEANING"
      ],
      "excluded_from_opportunity_reasoning":removed,
      "remaining_data_quality_uncertainties":quality,
      "material_unknown":"AUTHORITATIVE_PROPERTY_OR_ASSESSMENT_FACT_EXPLAINING_WHY_IMPROVEMENT_TO_LAND_ALLOCATION_IS_UNUSUAL",
      "single_next_fact":"VERIFY_CURRENT_IMPROVEMENT_CHARACTERISTICS_AND_ASSESSMENT_RECORD_MEANING_FOR_THIS_PARCEL",
      "next_research_route":"TARGETED_PROPERTY_ASSESSMENT_FACT_LOOKUP",
      "machine_research_first":True,
      "seller_intent":"UNKNOWN",
      "contact_authorized":False,
      "marketing_relevant_characteristics_status":"PRESERVE_FOR_LATER_ONLY_AFTER_FACT_VERIFICATION"
    }


def build_assessment_improvement_fact_resolution_v1():
    base=build_property_research_router_v1()
    all_cases=base.get("routed_cases") or []
    targets=[c for c in all_cases if c.get("research_route")==TARGET_ROUTE]
    resolved=[_resolve(c) for c in targets]
    expected=(base.get("summary") or {}).get("research_routes",{}).get(TARGET_ROUTE,0)
    ids=[x.get("parcel_id") for x in resolved if x.get("parcel_id")]
    states=Counter(x["resolution_state"] for x in resolved)
    reconciliation={
      "expected_target_cases":expected,
      "target_cases_received":len(targets),
      "cases_resolved":len(resolved),
      "unique_target_parcels":len(set(ids)),
      "duplicate_target_parcels":sorted({pid for pid in ids if ids.count(pid)>1}),
      "all_target_cases_accounted_for":expected==len(targets)==len(resolved)==len(set(ids))
    }
    ok=reconciliation["all_target_cases_accounted_for"] and expected==24
    return {
      "status":"ok" if ok else "reconciliation_failed",
      "version":VERSION,
      "mode":"READ_ONLY_TARGETED_FACT_RESOLUTION",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "source_checkpoint":{"router_version":base.get("version"),"router_cases":len(all_cases),"target_route":TARGET_ROUTE},
      "semantics_contract":{
        "full_market_value":"PROHIBITED_AS_OPPORTUNITY_EVIDENCE_CURRENT_DATASET_ZERO_POPULATION_WIDE",
        "assessed_total":"USABLE_AS_ASSESSMENT_COMPONENT_NOT_MARKET_PRICE",
        "assessed_land":"USABLE_AS_ASSESSMENT_COMPONENT_NOT_MARKET_PRICE",
        "full_baths_zero":"PLAUSIBILITY_WARNING_NOT_OPPORTUNITY_SIGNAL",
        "property_class":"PEER_GROUPING_KEY_CLASS_CODE_MEANING_SEPARATE_LOOKUP"
      },
      "summary":{"target_cases":len(resolved),"resolution_states":dict(states),"machine_research_first":sum(1 for x in resolved if x["machine_research_first"])},
      "reconciliation":reconciliation,
      "resolved_cases":resolved,
      "policy":{
        "data_quality_is_not_opportunity_evidence":True,
        "invalid_value_fields_removed_from_why_pmi_found_it":True,
        "missing_information_nonblocking":True,
        "machine_research_before_human":True,
        "seller_intent_inferred":False,
        "marketing_execution":False
      },
      "database_writes":0,
      "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"RUN_ONE_TARGETED_PROPERTY_ASSESSMENT_FACT_LOOKUP_USING_EXISTING_EVIDENCE_FIRST; DO_NOT_BULK_MANUAL_REVIEW"
    }
