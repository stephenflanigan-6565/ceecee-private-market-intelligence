#!/usr/bin/env python3
from collections import Counter
from datetime import datetime,timezone
from find2 import build_find2
VERSION='FIND3'

def _triage(c):
    a=c.get('actual_values') or {}; p=c.get('peer_context') or {}; rel=c.get('observed_relationships') or []
    imp=a.get('improvement_assessment'); sqft=a.get('living_sqft'); acres=a.get('acres')
    reasons=[]; contradictions=[]; next_fact=None; state='SURVIVES_CAUSAL_TRIAGE'; family='CORROBORATED_LAND_DOMINANCE'
    # A zero parcel-level improvement allocation is not itself evidence of vacant/minimal improvement.
    if imp == 0:
        if sqft is not None and sqft > 2500:
            state='NEEDS_TARGETED_FACT'; family='PROPERTY_FORM_OR_ASSESSMENT_SEMANTIC_CONFLICT'
            contradictions.append('ZERO_IMPROVEMENT_ASSESSMENT_CONTRADICTED_BY_SUBSTANTIAL_RECORDED_LIVING_SQFT')
            next_fact='Verify authoritative parcel use/property form and assessment allocation before treating zero improvement as land opportunity evidence.'
        else:
            state='NEEDS_TARGETED_FACT'; family='ZERO_IMPROVEMENT_REQUIRES_PROPERTY_FORM_CHECK'
            contradictions.append('ZERO_IMPROVEMENT_ASSESSMENT_NOT_SUFFICIENT_TO_PROVE_VACANT_OR_MINIMALLY_IMPROVED_PROPERTY')
            next_fact='Verify authoritative current improvement and parcel-use/property-form facts.'
    elif sqft in (None,0):
        state='NEEDS_TARGETED_FACT'; family='PHYSICAL_FIELD_GAP_OR_CONFLICT'
        contradictions.append('PHYSICAL_IMPROVEMENT_FIELD_MISSING_OR_ZERO_WHILE_ASSESSMENT_SHOWS_NONZERO_IMPROVEMENT')
        next_fact='Verify authoritative current building/improvement facts; do not infer vacancy from missing or zero living-area data.'
    else:
        reasons.append('NONZERO_IMPROVEMENT_ASSESSMENT_CONFIRMS_AN_IMPROVEMENT_IS_RECOGNIZED')
        if p.get('improvement_to_land_percentile') is not None and p['improvement_to_land_percentile'] <= .10:
            reasons.append('IMPROVEMENT_TO_LAND_RELATIONSHIP_REMAINS_EXTREME_WITHIN_SAME_PROPERTY_CLASS')
        if p.get('land_share_percentile') is not None and p['land_share_percentile'] >= .90:
            reasons.append('LAND_SHARE_REMAINS_HIGH_WITHIN_SAME_PROPERTY_CLASS')
        if 'SMALL_IMPROVEMENT_RELATIVE_TO_CLASS' in rel:
            reasons.append('RECORDED_LIVING_AREA_CORROBORATES_SMALL_IMPROVEMENT_RELATIVE_TO_CLASS')
        if 'EXCESS_OR_OVERSIZED_LAND_CONTEXT' in rel:
            reasons.append('ACREAGE_IS_LARGE_RELATIVE_TO_SAME_CLASS_PEERS')
        next_fact='Verify the single highest-value site/use constraint or redevelopment fact that could destroy the land-utilization thesis.'
    # Internal evidence cannot causally close the route merely because a field is missing/conflicted.
    return {
      'parcel_id':c.get('parcel_id'),'property_address':c.get('property_address'),'property_class':c.get('property_class'),
      'route':'LAND_PROPERTY_UTILIZATION','triage_state':state,'causal_family':family,
      'observed_relationships':rel,'supporting_internal_evidence':reasons,'contradictions_or_quality_flags':contradictions,
      'actual_values':a,'peer_context':p,'seller_intent':'UNKNOWN','contact_authorized':False,
      'why_pmi_noticed_it':'Land/improvement economics are unusually land-dominant relative to compatible property-class peers.',
      'why_it_still_deserves_attention':('The relationship survives internal causal triage but still requires a targeted site/use fact.' if state=='SURVIVES_CAUSAL_TRIAGE' else 'The numerical relationship is retained in memory, but a data/property-form question must be resolved before promotion.'),
      'highest_information_value_question':next_fact,
      'integration_rule':'ROUTE_STATE_CHANGES_DO_NOT_KILL_PROPERTY_OR_OTHER_INDEPENDENT_ROUTES'
    }

def build_find3():
    base=build_find2(); src=base.get('candidates') or []
    tri=[_triage(c) for c in src]
    counts=Counter(x['triage_state'] for x in tri); fams=Counter(x['causal_family'] for x in tri)
    # FIND2 currently exposes the first 40 diagnostic candidates. FIND3 is explicit about this scope.
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_LAND_PROPERTY_CAUSAL_TRIAGE','generated_at':datetime.now(timezone.utc).isoformat(),
      'scope':{'find2_whole_market_candidate_count':base.get('summary',{}).get('candidate_properties'),
               'triaged_records_returned_by_find2_payload':len(src),
               'important':'FIND3_TRIAGES_THE_FIND2_EXPOSED_DIAGNOSTIC_SET_ONLY; IT_DOES_NOT_CLAIM_CAUSAL_RESOLUTION_OF_ALL_153'},
      'triage_policy':{
        'zero_improvement_is_not_vacancy_proof':True,'missing_or_zero_physical_fields_are_not_opportunity_proof':True,
        'causal_kill_requires_explanatory_evidence':True,'internal_corroboration_may_keep_route_alive':True,
        'unknown_or_targeted_fact_is_valid_state':True,'route_kill_never_equals_property_kill':True,
        'assessment_components_are_supporting_economic_evidence_only':True,'seller_intent_inferred':False},
      'summary':{'triage_state_counts':dict(counts),'causal_family_counts':dict(fams)},
      'profiles':tri,
      'representative_external_research_lessons_not_applied_as_database_fact':[
        {'lesson':'SUBSTANTIAL_RECORDED_BUILDING_PLUS_ZERO_PARCEL_IMPROVEMENT_CAN_SIGNAL_PROPERTY_FORM_OR_ASSESSMENT_SEMANTICS','production_rule':'REQUIRE_AUTHORITATIVE_PROPERTY_FORM_OR_ASSESSMENT_ALLOCATION_BEFORE_ROUTE_KILL'},
        {'lesson':'SMALL_REAL_IMPROVEMENT_ON_LAND_DOMINANT_DUNE_PARCEL_CAN_BE_A_REAL_RELATIONSHIP','production_rule':'KEEP_ROUTE_ALIVE_WHEN_INTERNAL_BUILDING_AND_ASSESSMENT_FACTS_CORROBORATE; THEN_TEST_SITE_USE_CONSTRAINT'},
        {'lesson':'ZERO_OR_MISSING_LIVING_AREA_CAN_CONFLICT_WITH_REAL_WORLD_BUILDING_PRESENCE','production_rule':'DOWNGRADE_TO_NEEDS_TARGETED_FACT; NEVER_STRENGTHEN_VACANCY_HYPOTHESIS_FROM_ZERO_FIELD_ALONE'}],
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False,'closed_class_210_routes_reopened':False},
      'database_writes':0,
      'next_if_verified':'SCALE_CAUSAL_TRIAGE_ACROSS_ALL_FIND2_CANDIDATES_WITHOUT_TRUNCATION; THEN_INTEGRATE_ONLY_SURVIVING_OR_TARGETED_FACT_LAND_ROUTES_INTO_PROPERTY_CENTRIC_FIND_PROFILE'
    }
