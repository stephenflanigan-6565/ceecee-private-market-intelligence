#!/usr/bin/env python3
from datetime import datetime, timezone
from class_210_causal_scale_v1 import build_class_210_causal_scale_v1
VERSION='CLASS_210_EVIDENCE_FAMILY_SCREEN_V1'

# Corroborated public-record/property-history facts established during the research pass.
# This endpoint itself performs no external calls and writes nothing.
EVIDENCE={
'0905010000600023000': {'address':'7 JESSUP LN','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2023,'note':'Current improvement profile follows recent construction; redevelopment timing is materially relevant.'},
'0905015000400001000': {'address':'89 SEAFIELD LN','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2024,'before_improvement':61000.0,'after_improvement':6576400.0,'note':'Very large improvement reset aligned with current 2024 structure.'},
'0905015000200025000': {'address':'67 BEACH LN','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2023,'before_improvement':1135200.0,'after_improvement':4360900.0,'note':'Large post-construction improvement increase.'},
'0905008000300008003': {'address':'250 MILL RD','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2021,'before_improvement':207900.0,'after_improvement':3578000.0,'note':'2021 construction aligned with major improvement-assessment jump.'},
'0905003000200027003': {'address':'17 ADAM LN','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2022,'note':'2022 structure and sharp assessment reset support redevelopment explanation.'},
'0905006000100004002': {'address':'3 MORRIS CT','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2022,'before_total':290000.0,'after_total':1074300.0,'note':'Construction/redevelopment-era assessment expansion is material.'},
'0905002000200018000': {'address':'81 HAZELWOOD AVE','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2020,'before_improvement':186300.0,'after_improvement':695500.0,'note':'2020 construction aligned with substantial improvement-component expansion.'},
'0905008000200015002': {'address':'255 MILL RD','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2018,'before_improvement':0.0,'after_improvement':1546200.0,'note':'Vacant/near-vacant improvement component followed by new construction and large improvement assessment.'},
'0905013000100024003': {'address':'63 GRIFFING AVE','family':'REDEVELOPMENT_WITH_SOURCE_CONTRADICTION','year_built_current_record':2023,'legacy_year_built_feed':1953,'before_improvement':1700.0,'after_improvement':1462500.0,'note':'Assessment pattern strongly suggests redevelopment, but conflicting year-built feeds must remain explicit.'},
'0905009000300017009': {'address':'14 MICHAELS WAY','family':'REDEVELOPMENT_DISCONTINUITY_STRONG','year_built':2020,'before_improvement':0.0,'after_improvement':833100.0,'note':'New-construction record plus improvement reset supports redevelopment explanation.'},
'0905011000300031000': {'address':'58 LIBRARY AVE','family':'LONG_STABLE_IMPROVEMENT_HISTORY','year_built':1998,'stable_improvement':726600.0,'note':'Long stable improvement assessment does not fit recent redevelopment-discontinuity kill pattern.'},
'0905008000100024000': {'address':'104 ONECK LN','family':'STAGED_CHANGE_NOT_NARROW_CAUSAL_KILL','year_built':2019,'note':'Assessment rises in stages; newer year built alone is insufficient for causal kill.'},
}

def build_class_210_evidence_family_screen_v1():
    cp=build_class_210_causal_scale_v1()
    pending=[x for x in cp.get('cases',[]) if x.get('state')=='INSUFFICIENT_CAUSAL_EVIDENCE_PRESERVE_PENDING_EXISTING_DATA_FIRST']
    out=[]; counts={}
    for x in pending:
        pid=x['parcel_id']; ev=EVIDENCE.get(pid)
        if not ev:
            family='UNRESOLVED_REQUIRES_NEXT_FACT'
            state='PRESERVE_ASSESSMENT_ROUTE_TARGETED_FACT_REQUIRED'
            survives=True
            next_need='ONE_HIGH_INFORMATION_VALUE_PROPERTY_OR_ASSESSMENT_HISTORY_FACT; DO_NOT INFER CAUSALITY'
        else:
            family=ev['family']
            if family=='REDEVELOPMENT_DISCONTINUITY_STRONG':
                state='REDEVELOPMENT_CAUSAL_FAMILY_SUPPORTED_KILL_ASSESSMENT_ROUTE_ONLY'; survives=False
                next_need='NO_MORE_ASSESSMENT_CAUSE_RESEARCH_UNLESS_INDEPENDENT_ROUTE_REQUIRES_IT'
            elif family=='REDEVELOPMENT_WITH_SOURCE_CONTRADICTION':
                state='REDEVELOPMENT_PATTERN_STRONG_BUT_CONTRADICTION_MUST_BE_RECONCILED'; survives=True
                next_need='RECONCILE_CONFLICTING_YEAR_BUILT_OR_IMPROVEMENT_HISTORY_BEFORE_ROUTE_KILL'
            else:
                state='CAUSAL_KILL_NOT_PROVEN_PRESERVE_ASSESSMENT_ROUTE'; survives=True
                next_need='DIFFERENT_CAUSAL_EXPLANATION_REQUIRED; DO_NOT FORCE_REDEVELOPMENT_PATTERN'
        counts[family]=counts.get(family,0)+1
        row={'parcel_id':pid,'property_address':x['property_address'],'property_class':'210','evidence_family':family,'state':state,'assessment_route_survives':survives,'seller_intent':'UNKNOWN','contact_authorized':False,'independent_other_routes_preserved':True,'next_research_need':next_need}
        if ev: row['corroborated_context']=ev
        out.append(row)
    kills=sum(not r['assessment_route_survives'] for r in out)
    unresolved=sum(r['assessment_route_survives'] for r in out)
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_EVIDENCE_FAMILY_SCREEN','generated_at':datetime.now(timezone.utc).isoformat(),
      'source_checkpoint':{'version':cp.get('version'),'pending_cases_received':len(pending)},'cases':out,
      'summary':{'pending_cases_screened':len(out),'assessment_route_kills_supported':kills,'assessment_routes_preserved':unresolved,'evidence_family_counts':counts,'endpoint_external_calls':0},
      'decision':{'bulk_external_lookup_authorized':False,'proven_redevelopment_family_may_kill_assessment_route_only':True,'contradictions_block_route_kill':True,'stable_or_staged_history_remains_alive':True,'unknown_cases_remain_alive':True},
      'next_if_verified':'REMOVE_SUPPORTED_REDEVELOPMENT_CAUSAL_FAMILY_FROM_ASSESSMENT_ROUTE; RECONCILE CONTRADICTION CASE; THEN TARGET ONLY THE SMALL UNRESOLVED REMAINDER WITH HIGH_INFORMATION_VALUE FACTS',
      'policy':{'kill_route_not_property':True,'causal_evidence_required':True,'newer_year_built_alone_not_sufficient':True,'conflicting_source_facts_are_first_class':True,'missing_information_nonblocking':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}
