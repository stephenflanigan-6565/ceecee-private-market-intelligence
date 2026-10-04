#!/usr/bin/env python3
from collections import Counter
from datetime import datetime, timezone
from find7 import build_find7

VERSION='FIND9'

# Verified live FIND8S geometric evidence checkpoint, 2026-10-04.
# This is intentionally a compact evidence overlay, not a new source crawl.
# Shares are geometric facts only and never entitlement/buildability/use proof.
GEOMETRY={
'0905005000100021000': {'address':'30 LILAC RD','shares':{'R4':0.000518,'R2':0.999475}},
'0905005000100034000': {'address':'31 MAPLE ST','shares':{'R4':0.999555,'R2':0.000445}},
'0905008000200019000': {'address':'221 MILL RD','shares':{'HC':0.0,'B1':0.0,'R2':1.0}},
'0905008000200022000': {'address':'12 SCHOOL ST','shares':{'HC':0.0,'R2':1.0}},
'0905010000400036001': {'address':'6 BAYFIELD CT','shares':{'PC':0.0,'R1':1.0}},
'0905011000200039000': {'address':'17 LIBRARY AVE','shares':{'MF20':1.0,'HC':0.0}},
'0905011000200040000': {'address':'19 LIBRARY AVE','shares':{'MF20':1.0,'HC':0.0}},
'0905011000300027000': {'address':'70 LIBRARY AVE','shares':{'MF20':0.0,'R1':1.0}},
'0905012000400011000': {'address':'20 GLOVERS LN','shares':{'HC':1.0,'B1':0.0}},
'0905012000400013000': {'address':'16 GLOVERS LN','shares':{'HC':1.0,'B1':0.0}},
'0905017000100007001': {'address':'442 DUNE RD','shares':{'R3':1.0,'R5':0.0}},
'0905017000300006000': {'address':'15 POINT RD','shares':{'R3':0.0,'R5':1.0}},
'0905017000300055001': {'address':'400 DUNE RD','shares':{'R3':1.0,'R5':0.0}},
'0905017000500013000': {'address':'439 DUNE RD','shares':{'R3':0.999999,'R5':0.0}},
'0905017000500049000': {'address':'401 DUNE RD','shares':{'R3':0.0,'R5':1.0}},
'0905017000500050000': {'address':'399 DUNE RD','shares':{'R3':1.0,'R5':0.0}},
'0905017000500052001': {'address':'391 DUNE RD','shares':{'PC':0.0,'R3':1.0}},
'0905021000300011002': {'address':'107 DUNE RD','shares':{'PC':0.0,'R3':1.0}},
}
UNKNOWN={
'0905010000500021000': {'address':'27 STACY DR','reason':'FIND8S_SOURCE_REQUEST_TIMEOUT_NONBLOCKING'},
'0905010000700029000': {'address':'16 E DIVISION ST','reason':'NOT_RETURNED_IN_FIND8S_LIVE_RUN_PRESERVE_UNKNOWN_NONBLOCKING'},
}

# A <=0.1% secondary share is treated as an edge/sliver condition for research
# prioritization only. It is still preserved numerically and is not a legal conclusion.
SLIVER_MAX=0.001

def _classify(shares):
    positive={z:s for z,s in shares.items() if s and s>0}
    if not positive:
        return 'GEOMETRY_PRESENT_NO_POSITIVE_SHARE'
    ordered=sorted(positive.items(), key=lambda kv: kv[1], reverse=True)
    dominant_zone, dominant_share=ordered[0]
    secondary=sum(v for _,v in ordered[1:])
    if secondary <= SLIVER_MAX:
        return 'GEOMETRICALLY_EFFECTIVE_SINGLE_ZONE'
    return 'MATERIAL_MULTI_ZONE_GEOMETRY'

def build_find9(include_all_profiles=False):
    f7=build_find7(include_all_profiles=True)
    profiles=[]; geom_states=Counter(); question_states=Counter()
    for p0 in f7.get('profiles') or []:
        p=dict(p0); pid=p.get('parcel_id')
        if pid in GEOMETRY:
            g=GEOMETRY[pid]; shares=g['shares']; cls=_classify(shares)
            ordered=sorted(shares.items(), key=lambda kv: kv[1], reverse=True)
            p['geometric_zone_applicability']={
              'source_checkpoint':'FIND8S_LIVE_VERIFIED_2026_10_04',
              'evidence_state':'RESOLVED',
              'classification':cls,
              'zone_area_shares':shares,
              'dominant_zone':ordered[0][0] if ordered else None,
              'dominant_share':ordered[0][1] if ordered else None,
              'sliver_threshold_for_research_priority_only':SLIVER_MAX,
              'interpretation':'GEOMETRIC_FACT_ONLY_NOT_ENTITLEMENT_BUILDABILITY_OR_LAWFUL_USE'}
            geom_states[cls]+=1
            old=p.get('what_site_use_evidence_changes') or []
            revised=[]
            for x in old:
                if x in ('LAND_ROUTE_REQUIRES_ZONE_BOUNDARY_APPLICABILITY_REVIEW','LAND_ROUTE_REQUIRES_CONSERVATION_OR_OPEN_SPACE_APPLICABILITY_REVIEW'):
                    continue
                revised.append(x)
            if cls=='GEOMETRICALLY_EFFECTIVE_SINGLE_ZONE':
                revised.append('PRIOR_MULTI_ZONE_OR_CONSERVATION_BOUNDARY_SIGNAL_EXPLAINED_BY_GEOMETRY')
            else:
                revised.append('MATERIAL_MULTI_ZONE_GEOMETRY_REMAINS_RESEARCH_RELEVANT')
            p['what_site_use_evidence_changes']=revised
            lr=p.get('land_route') or {}
            if p.get('current_find_state')=='TARGETED_FACT_REQUIRED':
                p['next_best_property_question']=lr.get('next_question') or 'VERIFY_AUTHORITATIVE_CURRENT_PROPERTY_FORM_OR_IMPROVEMENT_FACT'
            elif cls=='MATERIAL_MULTI_ZONE_GEOMETRY':
                p['next_best_property_question']='WHAT_LAWFUL_USE_DIMENSIONAL_OR_ENVIRONMENTAL_RULES_MATERIALLY_CHANGE_THE_PROPERTY_HYPOTHESIS_WITHIN_THE_RESOLVED_ZONE_PATTERN'
            else:
                p['next_best_property_question']=lr.get('next_question') or 'NO_ADDITIONAL_GEOMETRY_RESEARCH_REQUIRED'
        elif pid in UNKNOWN:
            p['geometric_zone_applicability']={'source_checkpoint':'FIND8S_LIVE_2026_10_04','evidence_state':'UNKNOWN_NONBLOCKING',**UNKNOWN[pid]}
            geom_states['UNKNOWN_NONBLOCKING']+=1
            # Do not create another GIS hunt merely because the source timed out / omitted one target.
            lr=p.get('land_route') or {}
            p['next_best_property_question']=lr.get('next_question') or p.get('next_best_property_question')
        else:
            p['geometric_zone_applicability']={'evidence_state':'NOT_APPLICABLE_NO_FIND8_TARGET'}
        question_states[p.get('next_best_property_question') or 'UNKNOWN']+=1
        profiles.append(p)
    display=profiles if include_all_profiles else profiles[:40]
    return {
      'status':'ok','version':VERSION,
      'mode':'READ_ONLY_PROPERTY_CENTRIC_FIND_PROFILE_WITH_VERIFIED_GEOMETRIC_ZONE_APPLICABILITY',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'INTEGRATE_VERIFIED_FIND8S_GEOMETRIC_EVIDENCE_INTO_THE_FIND7_PROPERTY_CHASSIS_AND_REMOVE_FALSE_BOUNDARY_COMPLEXITY_WITHOUT_ERASING_WHY_PMI_NOTICED_IT',
      'source_checkpoints':{'find7':f7.get('version'),'find8s_live_verified':'2026-10-04','find8s_resolved_geometry_records':18,'find8s_unknown_nonblocking_records':2},
      'summary':{'unified_property_profiles':len(profiles),'geometry_integration_states':dict(geom_states),'next_best_question_distribution':dict(question_states),
                 'geometry_data_hunt_closed':True,'next_research_priority':'AUTHORITATIVE_CURRENT_PROPERTY_OR_IMPROVEMENT_FORM_FOR_EXISTING_TARGETED_FACT_CASES'},
      'profiles':display,
      'profile_payload':{'total':len(profiles),'returned':len(display),'complete':bool(include_all_profiles),'display_policy':'ALL_FOR_MACHINE_HANDOFF' if include_all_profiles else 'DETERMINISTIC_FIRST_40_BY_PARCEL_ID'},
      'interpretation_policy':{'data_serves_decision':True,'missing_geometry_nonblocking':True,'zero_area_boundary_touch_not_material_multi_zone':True,
        'tiny_sliver_preserved_but_not_automatic_complexity':True,'geometry_not_entitlement':True,'geometry_not_buildability':True,'geometry_not_lawful_use_proof':True,
        'why_found_history_preserved':True,'route_kill_never_equals_property_kill':True,'seller_intent_inferred':False,'unknown_valid_state':True},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,
        'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'PROMOTE FIND9 AS PROPERTY_INTELLIGENCE_CHASSIS; THEN TEST ONE AUTHORITATIVE CURRENT_PROPERTY_OR_IMPROVEMENT_FORM FACT ONLY FOR THE EXISTING TARGETED_FACT_REQUIRED CASES; DO_NOT START_A_GENERIC_DATA_HUNT'
    }

if __name__=='__main__':
    import json
    print(json.dumps(build_find9(),indent=2,sort_keys=True))
