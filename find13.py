#!/usr/bin/env python3
from collections import Counter
from datetime import datetime, timezone
from find9 import build_find9
from find12 import build_find12

VERSION='FIND13'
RAIL='IMPROVEMENT_AGE_MICRO_CORRIDOR_MISMATCH'

def _age_reason(c):
    return {
      'route':RAIL,
      'state':'ACTIVE_RESEARCH_ROUTE',
      'noticed_because':'IMPROVEMENT_AGE_IS_MATERIALLY_OUT_OF_STEP_WITH_OBSERVED_SAME_STREET_REINVESTMENT_CONTEXT',
      'observed_relationship':c.get('observed_relationship'),
      'subject_year_built':c.get('subject_year_built'),
      'street_context':c.get('street_context'),
      'street_year_built_median':c.get('street_year_built_median'),
      'subject_year_percentile_within_street':c.get('subject_year_percentile_within_street'),
      'materially_newer_street_peer_count':c.get('materially_newer_street_peer_count'),
      'street_valid_year_peer_count':c.get('street_valid_year_peer_count'),
      'example_materially_newer_street_properties':c.get('example_materially_newer_street_properties') or [],
      'next_question':'Does one existing property/improvement fact support or destroy the age-mismatch opportunity hypothesis without requiring a new data source?',
      'does_not_equal_seller_intent':True,
      'limits':['STREET_CONTEXT_IS_A_MICRO_CORRIDOR_PROXY_NOT_TRUE_ADJACENCY','YEAR_BUILT_IS_NOT_CONDITION','AGE_MISMATCH_IS_NOT_OBSOLESCENCE_OR_SELLER_INTENT'],
      'research_threshold_provenance':'FIND12_WHB_EXPERIMENTAL_OBSERVABILITY_ONLY_NOT_UNIVERSAL_RULES'
    }

def build_find13(include_all_profiles=False):
    f9=build_find9(include_all_profiles=True)
    f12=build_find12()
    age={str(c.get('parcel_id')):c for c in (f12.get('candidates') or [])}
    by={str(p.get('parcel_id')):dict(p) for p in (f9.get('profiles') or [])}
    overlap=0; novel=0
    # Overlay on existing profiles; preserve every prior WHY_FOUND reason.
    for pid,c in age.items():
        if pid in by:
            p=by[pid]
            reasons=list(p.get('why_pmi_noticed_it') or [])
            reasons.append(_age_reason(c)); p['why_pmi_noticed_it']=reasons
            attention=list(p.get('why_it_still_deserves_attention') or [])
            if RAIL not in attention: attention.append(RAIL)
            p['why_it_still_deserves_attention']=attention
            p['age_micro_corridor_context']=_age_reason(c)
            p['independent_discovery_rail_count']=sum(1 for r in reasons if r.get('route') not in ('OWNERSHIP_CONTEXT',))
            overlap+=1
        else:
            r=_age_reason(c)
            by[pid]={
              'parcel_id':pid,'property_address':c.get('property_address'),
              'owner_identity':{'names':[],'verification_state':'UNKNOWN_NOT_REQUIRED_FOR_DISCOVERY'},
              'current_find_state':'RESEARCH_ACTIVE','seller_intent':'UNKNOWN','contact_authorized':False,
              'why_pmi_noticed_it':[r], 'why_it_still_deserves_attention':[RAIL],
              'explained_or_closed_routes':[],
              'contradictions_and_unknowns':['PROPERTY_CONDITION_UNKNOWN','TRUE_ADJACENCY_UNKNOWN'],
              'authoritative_site_use_context':{'source_state':'NOT_YET_REQUIRED_FOR_THIS_HYPOTHESIS'},
              'geometric_zone_applicability':{'evidence_state':'NOT_REQUIRED_FOR_INITIAL_AGE_MISMATCH_DISCOVERY'},
              'age_micro_corridor_context':r,
              'next_best_property_question':r['next_question'],
              'independent_discovery_rail_count':1,
              'operator_contract':{'show_property':True,'show_owner_when_present':True,'explain_why_found':True,'score_exposed':False}
            }
            novel+=1
    profiles=sorted(by.values(),key=lambda p:str(p.get('parcel_id') or ''))
    rail_counts=Counter()
    multi=0
    for p in profiles:
        routes=set()
        for r in p.get('why_pmi_noticed_it') or []:
            rt=r.get('route')
            if rt and rt!='OWNERSHIP_CONTEXT': routes.add(rt);rail_counts[rt]+=1
        if len(routes)>1: multi+=1
    display=profiles if include_all_profiles else profiles[:40]
    return {
      'status':'ok','version':VERSION,
      'mode':'READ_ONLY_PROPERTY_INTELLIGENCE_CHASSIS_WITH_INDEPENDENT_AGE_MISMATCH_WHY_FOUND_RAIL',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'PROMOTE_FIND12_AS_AN_INDEPENDENT_WHY_FOUND_RAIL_AND_EXPAND_THE_PROPERTY_CENTRIC_FIND_UNIVERSE_WITHOUT_SCORING_OR_ENRICHMENT',
      'source_checkpoints':{'property_chassis':'FIND9','promoted_discovery_experiment':'FIND12','find12_observed_candidates':len(age)},
      'summary':{'prior_find9_profiles':len(f9.get('profiles') or []),'find12_candidates_integrated':len(age),
        'find12_overlap_existing_chassis':overlap,'find12_novel_profiles_added':novel,'unified_property_profiles':len(profiles),
        'profiles_with_multiple_independent_nonownership_why_found_routes':multi,'why_found_route_occurrences':dict(rail_counts)},
      'profiles':display,
      'profile_payload':{'total':len(profiles),'returned':len(display),'complete':bool(include_all_profiles),'display_policy':'ALL_FOR_MACHINE_HANDOFF' if include_all_profiles else 'DETERMINISTIC_FIRST_40_BY_PARCEL_ID'},
      'promotion_decision':{'find12':'PROMOTED_AS_INDEPENDENT_DISCOVERY_RAIL','reason':'17_OF_24_FIND12_CASES_WERE_NOVEL_TO_EXISTING_FIND1_FIND2_DISCOVERY_UNION','thresholds':'LOCAL_RESEARCH_PROVENANCE_ONLY_NOT_UNIVERSAL_RULES'},
      'interpretation_policy':{'data_serves_decision':True,'independent_why_found_reasons_preserved':True,'multi_rail_convergence_is_corroboration_not_seller_intent':True,
        'human_originated_opportunities_may_enter_same_property_intelligence_framework':True,'year_built_not_condition':True,'street_context_not_true_adjacency':True,
        'age_mismatch_not_obsolescence_proof':True,'route_kill_never_equals_property_kill':True,'unknown_valid_state':True,'no_generic_enrichment':True},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,
        'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'PROMOTE FIND13 AS THE EXPANDED PROPERTY_INTELLIGENCE_CHASSIS; THEN TEST THE NEXT GENUINELY_INDEPENDENT OPPORTUNITY FAMILY USING EXISTING EVIDENCE BEFORE ADDING ANY NEW DATA SOURCE.'
    }

if __name__=='__main__':
    import json
    print(json.dumps(build_find13(),indent=2,sort_keys=True))
