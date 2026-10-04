#!/usr/bin/env python3
from collections import Counter
from datetime import datetime, timezone
from find1 import build_find1, _ownership_snapshot
from find3 import build_find3

VERSION='FIND4'

def _land_route(x):
    targeted=x.get('triage_state')=='NEEDS_TARGETED_FACT'
    return {
      'route':'LAND_PROPERTY_UTILIZATION',
      'state':'TARGETED_FACT_REQUIRED' if targeted else 'ACTIVE_CORROBORATED_RESEARCH_ROUTE',
      'causal_family':x.get('causal_family'),
      'observed_relationships':x.get('observed_relationships') or [],
      'noticed_because':x.get('why_pmi_noticed_it'),
      'why_it_still_deserves_attention':x.get('why_it_still_deserves_attention'),
      'supporting_evidence':x.get('supporting_internal_evidence') or [],
      'contradictions_or_quality_flags':x.get('contradictions_or_quality_flags') or [],
      'next_question':x.get('highest_information_value_question'),
      'actual_values':x.get('actual_values') or {},
      'peer_context':x.get('peer_context') or {},
      'does_not_equal_seller_intent':True,
      'contact_authorized':False
    }

def build_find4(include_all_profiles=False):
    f1=build_find1()
    f3=build_find3(include_all_profiles=True)
    if not f3.get('summary',{}).get('coverage_complete'):
        raise RuntimeError('FIND3 full-population coverage is required before FIND4 integration')

    base={p.get('parcel_id'):dict(p) for p in (f1.get('profiles') or []) if p.get('parcel_id')}
    f1_ids=set(base)
    land={p.get('parcel_id'):p for p in (f3.get('profiles') or []) if p.get('parcel_id')}
    land_ids=set(land)
    new_ids=land_ids-f1_ids
    owners=_ownership_snapshot(new_ids)

    for pid,x in land.items():
        lr=_land_route(x)
        if pid not in base:
            names=owners.get(pid,[])
            base[pid]={
              'parcel_id':pid,'property_address':x.get('property_address'),
              'owner_identity':{'names':names,'verification_state':'UNKNOWN' if not names else 'UNVERIFIED_FROM_CURRENT_OWNERSHIP_MEMORY'},
              'why_pmi_noticed_it':[], 'why_it_still_deserves_attention':[], 'explained_or_closed_routes':[],
              'contradictions_and_unknowns':[], 'seller_intent':'UNKNOWN','contact_authorized':False,
              'operator_contract':{'show_property':True,'show_owner_when_present':True,'explain_why_found':True,'score_exposed':False}
            }
        p=base[pid]
        p.setdefault('why_pmi_noticed_it',[]).append(lr)
        if lr['state']=='ACTIVE_CORROBORATED_RESEARCH_ROUTE':
            p.setdefault('why_it_still_deserves_attention',[]).append('LAND_PROPERTY_UTILIZATION')
        else:
            p.setdefault('contradictions_and_unknowns',[]).extend(lr['contradictions_or_quality_flags'] or ['LAND_ROUTE_REQUIRES_TARGETED_FACT'])
        p['land_route']={'state':lr['state'],'causal_family':lr['causal_family'],'observed_relationships':lr['observed_relationships'],'next_question':lr['next_question']}

    states=Counter(); route_states=Counter(); profiles=[]
    for pid in sorted(base):
        p=base[pid]
        routes=p.get('why_pmi_noticed_it') or []
        for r in routes: route_states[r.get('state','UNKNOWN')]+=1
        active=any(r.get('state') in ('ACTIVE_RESEARCH_ROUTE','ACTIVE_CORROBORATED_RESEARCH_ROUTE') for r in routes)
        targeted=any(r.get('state')=='TARGETED_FACT_REQUIRED' for r in routes)
        if active: state='RESEARCH_ACTIVE'
        elif targeted: state='TARGETED_FACT_REQUIRED'
        else: state='NO_ACTIVE_ROUTE_FROM_CURRENT_INTEGRATED_RAILS'
        p['current_find_state']=state; states[state]+=1; profiles.append(p)

    overlap=f1_ids & land_ids
    summary={
      'unified_property_profiles':len(profiles),
      'find1_property_count':len(f1_ids),'find3_land_property_count':len(land_ids),
      'assessment_or_router_only_properties':len(f1_ids-land_ids),
      'land_only_properties':len(land_ids-f1_ids),'overlapping_properties':len(overlap),
      'land_routes_surviving_causal_triage':sum(1 for x in land.values() if x.get('triage_state')=='SURVIVES_CAUSAL_TRIAGE'),
      'land_routes_needing_targeted_fact':sum(1 for x in land.values() if x.get('triage_state')=='NEEDS_TARGETED_FACT'),
      'current_find_states':dict(states),'route_states':dict(route_states),
      'find3_coverage_complete':True
    }
    # Compact operator endpoint; machine handoff can request complete profile set internally.
    display=profiles if include_all_profiles else profiles[:40]
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_UNIFIED_PROPERTY_CENTRIC_FIND_PROFILE','generated_at':datetime.now(timezone.utc).isoformat(),
      'architecture':{
        'flow':['INDEPENDENT_DISCOVERY_ROUTES','EVIDENCE_STACK','CAUSAL_OR_CONTRADICTION_TESTS','UNION_BY_PARCEL','PROPERTY_OPPORTUNITY_PROFILE','VERIFICATION_GATE'],
        'property_centric_not_detector_centric':True,'independent_routes_preserved':True,'noticed_reason_preserved_after_route_close':True,
        'route_kill_never_equals_property_kill':True,'land_can_independently_enter_find':True,'title_or_ownership_cannot_independently_qualify':True,
        'seller_intent_not_required_for_property_opportunity_research':True,'operator_output_not_seller_score':True},
      'source_checkpoints':{'find1':f1.get('version'),'find3':f3.get('version'),'find3_full_population_coverage':True},
      'summary':summary,
      'profile_payload':{'total':len(profiles),'returned':len(display),'complete':bool(include_all_profiles),'display_policy':'ALL_FOR_MACHINE_HANDOFF' if include_all_profiles else 'DETERMINISTIC_FIRST_40_BY_PARCEL_ID'},
      'profiles':display,
      'policy':{'one_fact_not_seller':True,'assessment_route_close_does_not_block_land_route':True,'missing_information_nonblocking':True,'unknown_valid_state':True,'contradictions_first_class':True,'seller_intent_inferred':False,'marketing_execution':False,'score_or_rank_exposed':False},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False,'closed_class_210_routes_reopened':False},
      'next_if_verified':'PROMOTE FIND4 AS UNIFIED FIND CHASSIS; THEN ADD NEXT INDEPENDENT DISCOVERY RAIL OR TARGETED SITE_USE EVIDENCE LAYER BASED ON INFORMATION VALUE'
    }
