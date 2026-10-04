#!/usr/bin/env python3
from datetime import datetime, timezone
from residential_class_semantics_v1 import build_residential_class_semantics_v1

VERSION='CLASS_210_CAUSAL_SCALE_V1'

# External/public facts established before this endpoint. Endpoint itself makes no external calls.
ESTABLISHED={
 '0905008000300039000': {
   'property_address':'177 SUNSET AVE','resolution':'CAUSALLY_EXPLAINED_REDEVELOPMENT_DISCONTINUITY',
   'evidence':{'improvement_before':203500.0,'improvement_after':2388200.0,'improvement_multiple':11.735627,'land_stable':True,'construction_year':2021,'class_transition':'281_TO_210'},
   'basis':'MAJOR_REDEVELOPMENT + MATERIAL_IMPROVEMENT_ASSESSMENT_DISCONTINUITY + TEMPORAL_ALIGNMENT + CLASS_TRANSITION'
 },
 '0905008000200015001': {
   'property_address':'257 MILL RD','resolution':'CAUSALLY_EXPLAINED_REDEVELOPMENT_DISCONTINUITY',
   'evidence':{'improvement_before_2017':89300.0,'improvement_after_2018':2027200.0,'improvement_multiple':22.701008,'land_2017':417000.0,'land_2018':466100.0,'construction_year':2017,'current_class':'210'},
   'basis':'2017 CONSTRUCTION + 2017_TO_2018 IMPROVEMENT ASSESSMENT JUMP; LAND CHANGE IS SMALL RELATIVE TO IMPROVEMENT JUMP'
 },
 '0905012000300007000': {
   'property_address':'64 POTUNK LN','resolution':'UNRESOLVED_PRESERVE_ASSESSMENT_ROUTE',
   'evidence':{'long_assessment_history':True,'single_recent_discontinuity_proven':False,'assessment_2015':2249600.0,'assessment_2016':3681400.0,'assessment_2021':4190700.0,'assessment_2023':4184900.0},
   'basis':'MULTI_STAGE HISTORICAL ASSESSMENT CHANGES DO NOT SATISFY THE NARROW REDEVELOPMENT_DISCONTINUITY KILL PATTERN'
 }
}

def build_class_210_causal_scale_v1():
    cp=build_residential_class_semantics_v1()
    cases=[]
    eligible=[x for x in cp.get('cases',[]) if x.get('property_class')=='210' and x.get('survives_kill_test')]
    explained=0; unresolved=0; internal_only=0
    for x in eligible:
        pid=x.get('parcel_id'); established=ESTABLISHED.get(pid)
        if established:
            if established['resolution'].startswith('CAUSALLY_EXPLAINED'):
                state='ASSESSMENT_ROUTE_CAUSALLY_EXPLAINED_KILL_ROUTE_ONLY'; survives=False; explained+=1
                next_need='NO_FURTHER_ASSESSMENT_CAUSE_LOOKUP_UNLESS_INDEPENDENT_ROUTE_REQUIRES_IT'
                why=None
            else:
                state='CAUSAL_KILL_NOT_PROVEN_PRESERVE_ASSESSMENT_ROUTE'; survives=True; unresolved+=1
                next_need='TARGETED_DIFFERENT_CAUSAL_FACT_OR_HISTORICAL_ASSESSMENT_CONTEXT'
                why=x.get('why_pmi_found_it')
            cases.append({'parcel_id':pid,'property_address':x.get('property_address'),'property_class':'210','state':state,'assessment_route_survives':survives,'seller_intent':'UNKNOWN','contact_authorized':False,'external_context_already_established':established,'why_pmi_found_it':why,'independent_other_routes_preserved':True,'next_research_need':next_need})
        else:
            internal_only+=1
            cases.append({'parcel_id':pid,'property_address':x.get('property_address'),'property_class':'210','state':'INSUFFICIENT_CAUSAL_EVIDENCE_PRESERVE_PENDING_EXISTING_DATA_FIRST','assessment_route_survives':True,'seller_intent':'UNKNOWN','contact_authorized':False,'why_pmi_found_it':x.get('why_pmi_found_it'),'independent_other_routes_preserved':True,'next_research_need':'CHECK_EXISTING_PROPERTY_CONTEXT_TRANSFER_TITLE_AND_ASSESSMENT_HISTORY_FOR_REDEVELOPMENT_OR_CLASS_TRANSITION_BEFORE_EXTERNAL_LOOKUP'})
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_SCALED_CAUSAL_SCREEN','generated_at':datetime.now(timezone.utc).isoformat(),
      'source_checkpoint':{'version':cp.get('version'),'eligible_class_210_survivors':len(eligible)},
      'reusable_pattern':{'name':'REDEVELOPMENT_ASSESSMENT_DISCONTINUITY','required_evidence':['CORROBORATED_MAJOR_CONSTRUCTION_OR_REDEVELOPMENT','MATERIAL_IMPROVEMENT_ASSESSMENT_DISCONTINUITY','TEMPORAL_ALIGNMENT'],'stronger_when':['PROPERTY_CLASS_TRANSITION','LAND_COMPONENT_STABLE_OR_CHANGES_MUCH_LESS_THAN_IMPROVEMENT_COMPONENT'],'effect':'KILL_ASSESSMENT_ROUTE_ONLY'},
      'cases':cases,
      'summary':{'class_210_cases_screened':len(eligible),'causally_explained_route_kills':explained,'explicitly_tested_unresolved_preserved':unresolved,'pending_existing_data_first':internal_only,'external_lookups_performed_by_endpoint':0},
      'decision':{'bulk_external_lookup_authorized':False,'route_kills_require_proven_causality':True,'unresolved_cases_remain_alive':True,'independent_routes_always_preserved':True},
      'next_if_verified':'USE_INTERNAL EVIDENCE FIRST ACROSS PENDING CASES; BATCH ONLY HIGH_INFORMATION_VALUE EXTERNAL FACT LOOKUPS FOR CASES STILL UNRESOLVED AFTER INTERNAL SCREEN',
      'policy':{'causal_explanation_before_route_kill':True,'newer_year_built_alone_not_sufficient':True,'recent_sale_alone_not_sufficient':True,'missing_information_nonblocking':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}
    }
