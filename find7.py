#!/usr/bin/env python3
from collections import Counter
from datetime import datetime, timezone
from find4 import build_find4
from find6 import build_find6

VERSION='FIND7'

def build_find7(include_all_profiles=False):
    f4=build_find4(include_all_profiles=True)
    f6=build_find6()
    site={x.get('parcel_id'):x for x in (f6.get('profiles') or []) if x.get('parcel_id')}
    profiles=[]
    states=Counter(); site_states=Counter(); next_questions=Counter()
    for p0 in (f4.get('profiles') or []):
        p=dict(p0)
        s=site.get(p.get('parcel_id'))
        if s:
            z=s.get('zoning') or []
            flags=s.get('site_use_flags') or []
            p['authoritative_site_use_context']={
              'source_state':s.get('adapter_state'),
              'evidence_state':s.get('site_use_evidence_state'),
              'zoning':z,
              'flags':flags,
              'interpretation':'SITE_USE_CONTEXT_ONLY_NOT_ENTITLEMENT_OR_SELLER_INTENT'
            }
            site_states[s.get('site_use_evidence_state') or 'UNKNOWN']+=1
            # Keep discovery reason separate from what new evidence changes.
            impact=[]
            if 'CONSERVATION_OR_OPEN_SPACE_CONSTRAINT_SIGNAL' in flags:
                impact.append('LAND_ROUTE_REQUIRES_CONSERVATION_OR_OPEN_SPACE_APPLICABILITY_REVIEW')
            if 'MULTI_ZONE_INTERSECTION_REQUIRES_GEOMETRIC_APPLICABILITY_REVIEW' in flags:
                impact.append('LAND_ROUTE_REQUIRES_ZONE_BOUNDARY_APPLICABILITY_REVIEW')
            if 'COMMERCIAL_OR_HAMLET_MIXED_USE_CONTEXT' in flags:
                impact.append('LAND_ROUTE_REQUIRES_USE_AND_DIMENSIONAL_REGIME_REVIEW')
            if 'MULTIFAMILY_CONTEXT' in flags:
                impact.append('LAND_ROUTE_REQUIRES_PROPERTY_FORM_AND_PERMITTED_USE_REVIEW')
            if not impact:
                impact.append('ZONING_CONTEXT_RESOLVED_NO_ROUTE_CHANGE')
            p['what_site_use_evidence_changes']=impact
            # Next-best question: specific uncertainty, never an inferred entitlement.
            if any('CONSERVATION' in x for x in impact):
                nq='WHAT_PORTION_OF_THE_PARCEL_IS_SUBJECT_TO_CONSERVATION_OR_OPEN_SPACE_CONSTRAINT_AND_WHAT_BUILDABLE_AREA_REMAINS'
            elif any('ZONE_BOUNDARY' in x for x in impact):
                nq='WHAT_IS_THE_GEOMETRIC_APPLICABILITY_OF_EACH_ZONE_TO_THE_PARCEL_AND_EXISTING_IMPROVEMENT'
            elif any('USE_AND_DIMENSIONAL' in x for x in impact):
                nq='WHAT_CURRENT_LAWFUL_USE_AND_DIMENSIONAL_RULES_APPLY_TO_THIS_PARCEL'
            elif any('PROPERTY_FORM' in x for x in impact):
                nq='WHAT_IS_THE_CURRENT_LAWFUL_PROPERTY_FORM_AND_PERMITTED_USE'
            else:
                nq=(p.get('land_route') or {}).get('next_question') or 'NO_NEW_SITE_USE_QUESTION_REQUIRED'
            p['next_best_property_question']=nq
            next_questions[nq]+=1
        else:
            p['authoritative_site_use_context']={'source_state':'NOT_APPLICABLE_NO_FIND4_LAND_ROUTE'}
            p['what_site_use_evidence_changes']=[]
            p['next_best_property_question']='FOLLOW_EXISTING_NON_LAND_ROUTE_QUESTION'
        states[p.get('current_find_state') or 'UNKNOWN']+=1
        profiles.append(p)

    display=profiles if include_all_profiles else profiles[:40]
    return {
      'status':'ok','version':VERSION,
      'mode':'READ_ONLY_PROPERTY_CENTRIC_FIND_PROFILE_WITH_AUTHORITATIVE_SITE_USE_EVIDENCE',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'INTEGRATE_PROVEN_FIND6_SITE_USE_EVIDENCE_INTO_THE_UNIFIED_PROPERTY_PROFILE_WHILE_PRESERVING_WHY_FOUND_WHAT_CHANGED_AND_WHAT_REMAINS_UNKNOWN',
      'architecture':{
        'flow':['INDEPENDENT_DISCOVERY_ROUTES','WHY_PMI_NOTICED_IT','AUTHORITATIVE_EVIDENCE_STACK','WHAT_EVIDENCE_CHANGES','CONTRADICTIONS_AND_UNKNOWNS','NEXT_BEST_PROPERTY_QUESTION','VERIFICATION_GATE'],
        'property_centric_not_detector_centric':True,
        'why_found_preserved_separately_from_new_evidence':True,
        'route_kill_never_equals_property_kill':True,
        'site_use_evidence_not_seller_signal':True,
        'site_use_evidence_not_entitlement':True,
        'operator_output_not_score':True},
      'source_checkpoints':{'find4':f4.get('version'),'find6':f6.get('version'),
                            'find6_resolution_rate':f6.get('summary',{}).get('resolution_rate')},
      'summary':{
        'unified_property_profiles':len(profiles),
        'land_profiles_with_authoritative_site_use_context':len(site),
        'non_land_profiles_preserved':len(profiles)-len(site),
        'current_find_states':dict(states),
        'site_use_evidence_states':dict(site_states),
        'next_best_question_distribution':dict(next_questions)},
      'profile_payload':{'total':len(profiles),'returned':len(display),'complete':bool(include_all_profiles),
                         'display_policy':'ALL_FOR_MACHINE_HANDOFF' if include_all_profiles else 'DETERMINISTIC_FIRST_40_BY_PARCEL_ID'},
      'profiles':display,
      'policy':{
        'one_fact_not_seller':True,'zoning_not_entitlement':True,'multi_zone_not_automatic_opportunity':True,
        'constraint_signal_not_automatic_property_rejection':True,'missing_information_nonblocking':True,
        'unknown_valid_state':True,'seller_intent_inferred':False,'marketing_execution':False,
        'score_or_rank_exposed':False},
      'database_writes':0,
      'guards':{
        'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,
        'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,
        'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False,
        'closed_class_210_routes_reopened':False},
      'next_if_verified':'USE_FIND7_AS_PROPERTY_INTELLIGENCE_CHASSIS; SELECT_THE_NEXT_AUTHORITATIVE_CONSTRAINT_OR_PROPERTY_FORM_FACT_BY_INFORMATION_VALUE_FROM_THE_NEW_NEXT_BEST_QUESTIONS'
    }

if __name__=='__main__':
    import json
    print(json.dumps(build_find7(),indent=2,sort_keys=True))
