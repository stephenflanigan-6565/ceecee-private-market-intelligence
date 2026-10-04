#!/usr/bin/env python3
from datetime import datetime, timezone
from collections import Counter
from property_anomaly_explainer_v1 import build_property_anomaly_explainer_v1

VERSION="PROPERTY_RESEARCH_ROUTER_V1"

def _route(c):
    p=c.get("physical_context") or {}
    flags=set(p.get("context_flags") or [])
    pc=str(c.get("property_class") or "")
    addr=(c.get("property_address") or "").upper()
    missing=[]; quality=[]
    # Treat suspicious values as semantic uncertainty, never as opportunity evidence.
    if p.get("market_value") in (None,0): quality.append("MARKET_VALUE_FIELD_SEMANTICS_UNRESOLVED")
    if p.get("full_baths")==0 and (p.get("living_sqft") or 0)>=1500: quality.append("ZERO_FULL_BATHS_PLAUSIBILITY_CHECK")
    if p.get("building_style") in (None,"Unknown","UNKNOWN"): missing.append("BUILDING_STYLE")
    if p.get("living_sqft") is None: missing.append("LIVING_SQFT")
    if p.get("year_built") is None: missing.append("YEAR_BUILT")

    # First ask the fact with the greatest chance of explaining/killing the anomaly.
    if pc in {"311","312","314","315","323","464","971"} or "RIGHT OF WAY" in addr:
        route="VERIFY_PROPERTY_USE_AND_PARCEL_FUNCTION"
        question="What is the authoritative parcel use/function, and is the improvement assessment describing a real improvement on this parcel?"
    elif "NEWER_STRUCTURE_RELATIVE_TO_CLASS" in flags or "LARGE_STRUCTURE_RELATIVE_TO_CLASS" in flags:
        route="VERIFY_IMPROVEMENT_AND_ASSESSMENT_SEMANTICS"
        question="Do authoritative property/assessment facts confirm the current improvement, size/year, and land-versus-improvement allocation?"
    elif "HIGH_IMPROVEMENT_ASSESSMENT_RELATIVE_TO_CLASS" in flags:
        route="VERIFY_IMPROVEMENT_CHARACTERISTICS"
        question="What verified improvement characteristic explains the unusually high improvement value relative to land and comparable class peers?"
    else:
        route="VERIFY_SITE_OR_USE_DIFFERENCE"
        question="What verified site, use, or improvement fact explains why this parcel remains unusual among physical peers?"

    # Manual route is allowed but only when existing evidence cannot resolve a material fact.
    existing_disposition=c.get("disposition")
    if existing_disposition=="NEEDS_CEECEE_VERIFICATION":
        action="NEEDS_CEECEE_VERIFICATION"
    else:
        action="MACHINE_RESEARCH_FIRST"
    return {
      "parcel_id":c.get("parcel_id"),"property_address":c.get("property_address"),"property_class":c.get("property_class"),
      "current_disposition":existing_disposition,"research_route":route,"recommended_action":action,
      "highest_information_value_question":question,
      "data_quality_uncertainties":quality,"missing_context":missing,
      "opportunity_hypothesis":"PROPERTY_OR_LAND_RELATIONSHIP_REMAINS_UNEXPLAINED",
      "seller_intent":"UNKNOWN","contact_authorized":False,
      "manual_verification_rule":"MISSING_INFORMATION_DOES_NOT_KILL_SURVIVING_OPPORTUNITY; CEECEE_REVIEW_IS_EXCEPTION_PATH_BEFORE_MARKETING_WHEN_MATERIAL_FACT_REMAINS_UNRESOLVED"
    }

def build_property_research_router_v1():
    base=build_property_anomaly_explainer_v1()
    cases=base.get("inspection_cases") or []
    routed=[_route(c) for c in cases]
    rc=Counter(x["research_route"] for x in routed); ac=Counter(x["recommended_action"] for x in routed)
    qc=Counter(q for x in routed for q in x["data_quality_uncertainties"])
    return {
      "status":"ok","version":VERSION,"mode":"READ_ONLY_INFORMATION_VALUE_RESEARCH_ROUTER",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "source_checkpoint":{"version":base.get("version"),"base_a4_anomalies":base.get("summary",{}).get("base_a4_anomalies"),"surviving_or_verification_cases":base.get("summary",{}).get("surviving_or_verification_cases")},
      "summary":{"cases_routed":len(routed),"research_routes":dict(rc),"recommended_actions":dict(ac),"data_quality_uncertainties":dict(qc)},
      "policy":{"information_value_before_new_source":True,"machine_research_before_human_when_possible":True,"missing_information_nonblocking":True,"needs_ceecee_verification_valid":True,"manual_review_is_exception_path":True,"data_quality_is_not_opportunity_evidence":True,"seller_intent_inferred":False},
      "routed_cases":routed,
      "database_writes":0,
      "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"USE_ROUTING_COUNTS_AND_CASE_QUESTIONS_TO_SELECT_THE_FIRST_TARGETED_FACT_RESOLUTION_TEST_WITHOUT_BULK_MANUAL_REVIEW"
    }
