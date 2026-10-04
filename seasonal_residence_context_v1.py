#!/usr/bin/env python3
from datetime import datetime, timezone
from property_form_peer_context_v1 import build_property_form_peer_context_v1

VERSION='SEASONAL_RESIDENCE_CONTEXT_V1'

def build_seasonal_residence_context_v1():
    prior=build_property_form_peer_context_v1()
    if prior.get('status')!='ok':
        return {'status':'upstream_not_ok','version':VERSION,'upstream':prior,'database_writes':0}
    d=prior.get('peer_context_diagnostics',{})
    same=d.get('SAME_CLASS',{})
    dune=d.get('SAME_CLASS_DUNE_RD',{})
    small=d.get('DUNE_SMALL_LOT_PHYSICAL_CONTEXT',{})
    survives=bool(prior.get('resolution',{}).get('survives_contextual_peer_test'))
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_CLASS_SEMANTICS_AND_SCALING_GATE',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'target':prior.get('target'),
      'resolved_semantics':{
        'property_class_260':{
          'meaning':'SEASONAL_RESIDENCE',
          'status':'SEMANTICALLY_RESOLVED_FOR_REASONING',
          'does_not_prove':['CONDOMINIUM_OWNERSHIP','COOPERATIVE_OWNERSHIP','HOMEOWNERS_ASSOCIATION_MEMBERSHIP','SELLER_INTENT'],
          'reasoning_use':'VALID_PEER_GROUPING_AND_PROPERTY_CONTEXT'
        },
        'exact_legal_property_form':{
          'status':'UNRESOLVED_NONBLOCKING',
          'reasoning_use':'DO_NOT_ASSERT; RETAIN_AS_LOCAL_CONTEXT_HYPOTHESIS ONLY'
        }
      },
      'reinterpreted_peer_test':{
        'seasonal_residence_peer_count':same.get('peer_count'),
        'seasonal_residence_target_percentile':same.get('target_percentile'),
        'seasonal_dune_road_peer_count':dune.get('peer_count'),
        'seasonal_dune_road_target_percentile':dune.get('target_percentile'),
        'small_lot_physical_context_peer_count':small.get('peer_count'),
        'small_lot_physical_context_target_percentile':small.get('target_percentile'),
        'anomaly_survives_corrected_class_semantics':survives
      },
      'resolution':{
        'state':'CLASS_SEMANTICS_RESOLVED_ANOMALY_STILL_SURVIVES' if survives else 'CLASS_SEMANTICS_RESOLVED_REEVALUATE_ANOMALY',
        'why_pmi_found_it':'SEASONAL_RESIDENCE_HAS_UNUSUALLY_HIGH_IMPROVEMENT_TO_LAND_ASSESSMENT_RELATIONSHIP_RELATIVE_TO_SEASONAL_AND_DUNE_CONTEXT' if survives else 'ASSESSMENT_RELATIONSHIP_REQUIRES_FURTHER_CONTEXT',
        'seller_intent':'UNKNOWN',
        'legal_property_form_required_to_keep_case_alive':False if survives else None,
        'legal_property_form_still_useful_for_later_enrichment':True
      },
      'scaling_gate':{
        'method_ready_to_scale_beyond_target':survives,
        'allowed_next_scope':'APPLY_CORRECTED_CLASS_SEMANTICS_AND_CONTEXTUAL_PEER_KILL_TEST_TO_REMAINING_ASSESSMENT_ROUTE_CASES' if survives else 'KEEP_SINGLE_PROPERTY_RESEARCH',
        'do_not_scale':['SELLER_INTENT','CONTACT_AUTHORIZATION','UNVERIFIED_LEGAL_PROPERTY_FORM','FULL_MARKET_VALUE_ZERO_FIELD']
      },
      'policy':{
        'class_semantics_before_peer_interpretation':True,
        'local_human_context_preserved_as_hypothesis':True,
        'missing_legal_form_nonblocking':True,
        'data_quality_is_not_opportunity_evidence':True,
        'seller_intent_inferred':False,
        'marketing_execution':False
      },
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'IF_METHOD_READY_TO_SCALE, APPLY_THE_CORRECTED_CLASS_SEMANTICS_AND_CONTEXTUAL_PEER_KILL_TEST_TO_THE_REMAINING_ASSESSMENT_ROUTE_CASES_BEFORE_NEW_EXTERNAL_LOOKUPS'
    }
