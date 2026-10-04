#!/usr/bin/env python3
from datetime import datetime, timezone
from class_210_evidence_family_screen_v1 import build_class_210_evidence_family_screen_v1
VERSION='CLASS_210_TARGETED_REMAINDER_RESOLUTION_V1'

# Public-record facts established in the targeted research pass. No live external calls occur in endpoint.
TARGETED={
'0905008000100032002': {'address':'319 MILL RD','resolution':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2018,'assessment_history':{'2016_land':317600.0,'2016_improvement':0.0,'2017_improvement':826800.0,'2018_improvement':1189900.0,'2025_improvement':1485300.0},'meaning':'Land-only/near-land-only condition followed by large improvement component aligned with 2018 build.'},
'0905015000300002001': {'address':'66A BEACH LN','resolution':'LONG_STABLE_IMPROVEMENT_HISTORY','year_built':2004,'assessment_history':{'2014_improvement':2128400.0,'2021_improvement':2128400.0,'2024_improvement':2140300.0,'land':724000.0},'meaning':'Long-stable improvement history does not support recent redevelopment-discontinuity explanation.'},
'0905006000200011005': {'address':'32 ROGERS AVE','resolution':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2025,'year_renovated':2025,'current_land':290000.0,'current_improvement':974500.0,'meaning':'Current record identifies 2025 build/renovation with substantial additions component; redevelopment explanation supported.'},
'0905014000100009000': {'address':'21 SEAFIELD LN','resolution':'LONG_STABLE_OR_LEGACY_EXPANSION_HISTORY','year_built':1930,'expanded':1994,'assessment_history':{'2014_2022_total':3191600.0,'2023_total':3252000.0,'2025_total':3186900.0,'2025_land':900600.0,'2025_improvement':2286300.0},'meaning':'Legacy residence/1994 expansion and long-stable modern assessment do not support recent redevelopment-discontinuity explanation.'},
'0905013000100024003': {'address':'63 GRIFFING AVE','resolution':'ASSESSMENT_CAUSE_EXPLAINED_SOURCE_CONTRADICTION_RETAINED','current_year_built':2023,'legacy_year_built':1953,'before_improvement':1700.0,'after_improvement':1462500.0,'meaning':'Current-structure evidence plus assessment reset explains assessment route; conflicting legacy year-built remains an explicit property-history integrity flag rather than blocking causal resolution.'},
}

def build_class_210_targeted_remainder_resolution_v1():
    cp=build_class_210_evidence_family_screen_v1()
    cases=[]
    for x in cp.get('cases',[]):
        pid=x['parcel_id']
        if x.get('evidence_family') not in ('UNRESOLVED_REQUIRES_NEXT_FACT','REDEVELOPMENT_WITH_SOURCE_CONTRADICTION'):
            continue
        ev=TARGETED.get(pid)
        if not ev:
            cases.append({**x,'state':'TARGETED_FACT_NOT_ESTABLISHED_PRESERVE','assessment_route_survives':True})
            continue
        r=ev['resolution']
        if r in ('REDEVELOPMENT_DISCONTINUITY_STRONG','ASSESSMENT_CAUSE_EXPLAINED_SOURCE_CONTRADICTION_RETAINED'):
            survives=False
            state='ASSESSMENT_ROUTE_CAUSALLY_EXPLAINED_KILL_ROUTE_ONLY'
            next_need='NO_FURTHER_ASSESSMENT_CAUSE_RESEARCH; PRESERVE ANY INDEPENDENT ROUTES'
        else:
            survives=True
            state='REDEVELOPMENT_CAUSAL_KILL_NOT_PROVEN_PRESERVE_ASSESSMENT_ROUTE'
            next_need='DIFFERENT_CAUSAL_FAMILY_REQUIRED; DO NOT FORCE_REDEVELOPMENT_PATTERN'
        row={'parcel_id':pid,'property_address':x['property_address'],'property_class':'210','targeted_resolution':r,'state':state,'assessment_route_survives':survives,'seller_intent':'UNKNOWN','contact_authorized':False,'independent_other_routes_preserved':True,'next_research_need':next_need,'external_context_already_established':ev}
        if pid=='0905013000100024003':
            row['source_contradiction']={'status':'RETAINED_EXPLICITLY','field':'year_built','legacy_value':1953,'current_structure_value':2023,'blocks_assessment_route_resolution':False,'requires_future_property_history_reconciliation':True}
        cases.append(row)
    kills=sum(not x['assessment_route_survives'] for x in cases)
    preserved=sum(x['assessment_route_survives'] for x in cases)
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_TARGETED_REMAINDER_RESOLUTION','generated_at':datetime.now(timezone.utc).isoformat(),
      'source_checkpoint':{'version':cp.get('version'),'targeted_cases_received':len(cases)},'cases':cases,
      'summary':{'targeted_cases_resolved':len(cases),'assessment_route_kills_supported':kills,'assessment_routes_preserved_for_different_causal_research':preserved,'endpoint_external_calls':0},
      'decision':{'bulk_external_lookup_authorized':False,'redevelopment_explained_routes_stop_here':True,'stable_legacy_cases_remain_alive':True,'source_contradiction_may_be_retained_without_blocking_independently_proven_causal_resolution':True},
      'next_if_verified':'MERGE ROUTE-KILL RESULTS WITH PRIOR CLASS_210 SCREEN; ADVANCE ONLY PRESERVED COUNTEREXAMPLES TO DIFFERENT CAUSAL-FAMILY RESEARCH',
      'policy':{'kill_route_not_property':True,'causal_evidence_required':True,'source_contradictions_retained_explicitly':True,'missing_information_nonblocking':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}
