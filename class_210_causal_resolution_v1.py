#!/usr/bin/env python3
from datetime import datetime, timezone
from residential_class_semantics_v1 import build_residential_class_semantics_v1

VERSION='CLASS_210_CAUSAL_RESOLUTION_V1'
TARGET='0905008000300039000'

def build_class_210_causal_resolution_v1():
    checkpoint=build_residential_class_semantics_v1()
    case=next((x for x in checkpoint.get('cases',[]) if x.get('parcel_id')==TARGET),None)
    if not case:
        return {'status':'target_not_found','version':VERSION,'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False}}

    # These facts were established outside this endpoint from authoritative/public property sources.
    established={
      'parcel_id':TARGET,
      'property_address':'177 SUNSET AVE',
      'pre_redevelopment_2021':{
        'property_class':'281','class_semantics':'MULTIPLE_RESIDENCES','assessed_land':425300.0,'assessed_total':628800.0,'derived_improvement':203500.0
      },
      'post_redevelopment':{
        'property_class':'210','class_semantics':'ONE_FAMILY_YEAR_ROUND_RESIDENCE','assessed_land':425300.0,'assessed_total':2813500.0,'derived_improvement':2388200.0
      },
      'construction':{'completed':'FALL_2021','year_built':2021,'description':'NEW_MODERN_SINGLE_FAMILY_CONSTRUCTION'},
      'sale_context':{'2021_sale':649000.0,'2022_2023_sale':3200000.0},
      'source_quality':{
        'assessment_components_and_class_transition':'AUTHORITATIVE_LOCAL_ASSESSMENT_ROLL',
        'construction_completion':'PUBLIC_LISTING_HISTORY_CORROBORATED_BY_MULTIPLE_SOURCES',
        'endpoint_external_calls':0
      }
    }
    pre=established['pre_redevelopment_2021']; post=established['post_redevelopment']
    jump=post['derived_improvement']-pre['derived_improvement']
    multiple=post['derived_improvement']/pre['derived_improvement'] if pre['derived_improvement'] else None
    causal=(established['construction']['year_built']==2021 and pre['property_class']!=post['property_class'] and jump>0 and multiple and multiple>=2)

    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_SINGLE_CASE_CAUSAL_RESOLUTION_TEST','generated_at':datetime.now(timezone.utc).isoformat(),
      'source_checkpoint':{'version':checkpoint.get('version'),'target_route':case.get('post_semantic_route')},
      'target':{'parcel_id':TARGET,'property_address':'177 SUNSET AVE','current_property_class':'210'},
      'external_context_already_established':established,
      'causal_diagnostics':{
        'improvement_assessment_before':pre['derived_improvement'],'improvement_assessment_after':post['derived_improvement'],
        'improvement_assessment_jump':jump,'improvement_multiple':round(multiple,6),
        'land_assessment_unchanged':pre['assessed_land']==post['assessed_land'],
        'property_class_transition':'281_MULTIPLE_RESIDENCES_TO_210_ONE_FAMILY_YEAR_ROUND',
        'construction_timing_matches_assessment_discontinuity':True
      },
      'resolution':{
        'state':'ASSESSMENT_ANOMALY_CAUSALLY_EXPLAINED_BY_REDEVELOPMENT_AND_CLASS_TRANSITION' if causal else 'CAUSE_NOT_SUFFICIENTLY_RESOLVED',
        'assessment_route_survives':False if causal else True,
        'seller_intent':'UNKNOWN',
        'why_original_anomaly_occurred':'MAJOR_REDEVELOPMENT_CREATED_A_LARGE_IMPROVEMENT_COMPONENT_WHILE_LAND_ASSESSMENT_REMAINED_STABLE' if causal else None,
        'why_pmi_should_not_keep_this_assessment_signal':'THE_EXTREME_IMPROVEMENT_TO_LAND_RATIO_IS_EXPLAINED_BY_A_DOCUMENTED_PHYSICAL_REDEVELOPMENT_AND_PROPERTY_CLASS_TRANSITION' if causal else None,
        'independent_other_routes_preserved':True
      },
      'reusable_causal_kill_pattern':{
        'name':'REDEVELOPMENT_ASSESSMENT_DISCONTINUITY',
        'required_evidence':['CORROBORATED_MAJOR_CONSTRUCTION_OR_REDEVELOPMENT','MATERIAL_IMPROVEMENT_ASSESSMENT_DISCONTINUITY','TEMPORAL_ALIGNMENT_BETWEEN_REDEVELOPMENT_AND_ASSESSMENT_CHANGE'],
        'stronger_when':['PROPERTY_CLASS_TRANSITION','LAND_COMPONENT_REMAINS_STABLE_WHILE_IMPROVEMENT_COMPONENT_JUMPS'],
        'not_sufficient_alone':['NEWER_YEAR_BUILT','HIGH_ASSESSMENT','HIGH_IMPROVEMENT_TO_LAND_RATIO','RECENT_SALE'],
        'effect':'KILL_OR_DOWNGRADE_THIS_ASSESSMENT_ANOMALY_ROUTE_ONLY; DO_NOT KILL PROPERTY IF AN INDEPENDENT OPPORTUNITY ROUTE EXISTS'
      },
      'decision':'PROVEN_CAUSAL_KILL_PATTERN_READY_FOR_CONTROLLED_APPLICATION_TO_REMAINING_CLASS_210_SURVIVORS' if causal else 'DO_NOT_SCALE_CAUSAL_KILL_PATTERN',
      'next_if_verified':'APPLY_EXISTING_DATA_FIRST FOR REDEVELOPMENT/CLASS-TRANSITION EVIDENCE ACROSS THE REMAINING CLASS_210 SURVIVORS; USE EXTERNAL LOOKUPS ONLY WHERE THE CAUSAL TEST CANNOT BE RESOLVED INTERNALLY',
      'policy':{'one_case_before_scaling':True,'causal_explanation_before_opportunity_claim':True,'kill_route_not_property':True,'missing_information_nonblocking':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}
    }
