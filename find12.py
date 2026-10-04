#!/usr/bin/env python3
import os,re,json,math,statistics
from collections import defaultdict,Counter
from datetime import datetime,timezone
from find1 import build_find1
from find2 import build_find2,_payload,_flat,_pick,_num,ALIASES

VERSION='FIND12'; MARKET='WESTHAMPTON_BEACH_NY'
MIN_STREET_PEERS=8
MIN_YEAR_GAP=20
MIN_NEWER_PEERS=3
OLD_QUANTILE=.20

SUFFIX={'ROAD':'RD','AVENUE':'AVE','STREET':'ST','LANE':'LN','DRIVE':'DR','COURT':'CT','HIGHWAY':'HWY','BOULEVARD':'BLVD','PLACE':'PL','TERRACE':'TER'}
def _street(addr):
    if not addr:return None
    s=re.sub(r'[^A-Z0-9 ]+',' ',str(addr).upper()).strip()
    parts=s.split()
    if parts and re.match(r'^\d+[A-Z]?$',parts[0]): parts=parts[1:]
    if parts and parts[-1] in SUFFIX: parts[-1]=SUFFIX[parts[-1]]
    return ' '.join(parts) or None

def _pct(xs,x):
    if not xs:return None
    s=sorted(xs); return (sum(v<x for v in s)+.5*sum(v==x for v in s))/len(s)

def build_find12():
    import psycopg
    f1=build_find1(); f2=build_find2(include_all_candidates=True)
    covered=set(str(p.get('parcel_id')) for p in f1.get('profiles',[])) | set(str(p.get('parcel_id')) for p in f2.get('candidates',[]))
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor();cur.execute("""SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
          WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
          ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,['PROPERTY_CONTEXT','ASSESSMENT_CONTEXT']))
        rows=cur.fetchall()
    finally: conn.close()
    by=defaultdict(dict)
    for pid,fam,pj in rows:
        for k,v in _flat(_payload(pj)).items():
            if k not in by[str(pid)] and v not in (None,''):by[str(pid)][k]=v
    props=[]
    for pid,m in by.items():
        addr=_pick(m,ALIASES['address']); y=_num(_pick(m,ALIASES['year_built'])); pc=_pick(m,ALIASES['property_class'])
        if y is None or not (1600<=y<=datetime.now().year+1):continue
        st=_street(addr)
        if not st:continue
        props.append({'parcel_id':pid,'property_address':str(addr).strip() if addr else None,'street_context':st,
                      'property_class':str(pc).strip() if pc else None,'year_built':int(y)})
    streets=defaultdict(list)
    for p in props:streets[p['street_context']].append(p)
    cand=[]; excluded=Counter()
    for p in props:
        peers=[x for x in streets[p['street_context']] if x['parcel_id']!=p['parcel_id']]
        if len(peers)<MIN_STREET_PEERS: excluded['STREET_VALID_YEAR_PEERS_LT_8']+=1;continue
        yrs=[x['year_built'] for x in peers]; med=statistics.median(yrs); age_pct=_pct(yrs,p['year_built'])
        newer=[x for x in peers if x['year_built']>=p['year_built']+MIN_YEAR_GAP]
        if age_pct is None or age_pct>OLD_QUANTILE:continue
        if med-p['year_built']<MIN_YEAR_GAP or len(newer)<MIN_NEWER_PEERS:continue
        same_class=[x for x in peers if p['property_class'] and x['property_class']==p['property_class']]
        cand.append({'parcel_id':p['parcel_id'],'property_address':p['property_address'],'property_class':p['property_class'],
          'observed_relationship':'OLDER_IMPROVEMENT_RELATIVE_TO_SAME_STREET_PROPERTY_CONTEXT',
          'subject_year_built':p['year_built'],'street_context':p['street_context'],'street_valid_year_peer_count':len(peers),
          'street_year_built_median':med,'subject_year_percentile_within_street':round(age_pct,6),
          'materially_newer_street_peer_count':len(newer),'same_property_class_street_peer_count':len(same_class),
          'example_materially_newer_street_properties':[{'parcel_id':x['parcel_id'],'property_address':x['property_address'],'year_built':x['year_built']} for x in sorted(newer,key=lambda z:z['year_built'],reverse=True)[:4]],
          'existing_find1_find2_coverage':p['parcel_id'] in covered,
          'novel_to_existing_find1_find2_union':p['parcel_id'] not in covered,
          'hypothesis':'IMPROVEMENT_AGE_IS_MATERIALLY_OUT_OF_STEP_WITH_OBSERVED_SAME_STREET_REINVESTMENT_CONTEXT',
          'state':'OBSERVED_DISCOVERY_HYPOTHESIS','seller_intent':'UNKNOWN','contact_authorized':False,
          'next_question':'Does one existing property/improvement fact support or destroy the age-mismatch opportunity hypothesis without requiring a new data source?',
          'limits':['STREET_CONTEXT_IS_A_MICRO_CORRIDOR_PROXY_NOT_TRUE_ADJACENCY','YEAR_BUILT_IS_NOT_CONDITION','AGE_MISMATCH_IS_NOT_OBSOLESCENCE_OR_SELLER_INTENT']})
    cand.sort(key=lambda r:(not r['novel_to_existing_find1_find2_union'],r['subject_year_percentile_within_street'],-r['materially_newer_street_peer_count'],r['parcel_id']))
    novel=sum(1 for r in cand if r['novel_to_existing_find1_find2_union'])
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_INDEPENDENT_IMPROVEMENT_AGE_MICRO_CORRIDOR_DISCOVERY_EXPERIMENT',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_OU_022_OU_137_USING_ONLY_EXISTING_PROPERTY_CONTEXT_AND_ASSESSMENT_CONTEXT_WITHOUT_NEW_DATA_OR_SPATIAL_SOURCE',
      'architecture':{'opportunity_universe_family':'OU-022_IMPROVEMENT_AGE_CONDITION_MISMATCH / OU-137_OUTLIER_IMPROVEMENT_AGE_CONDITION',
        'independent_of_land_assessment_ratio_route':True,'property_not_seller_model':True,'street_context_is_proxy_not_adjacency':True,
        'human_originated_opportunities_can_enter_same_future_property_intelligence_framework':True},
      'summary':{'working_property_universe':f2.get('summary',{}).get('whole_market_properties'),'valid_year_and_street_records':len(props),
        'street_contexts':len(streets),'observed_age_mismatch_candidates':len(cand),'novel_to_existing_find1_find2_union':novel,
        'already_covered_by_existing_find1_find2_union':len(cand)-novel,'exclusions':dict(excluded)},
      'research_thresholds':{'status':'EXPERIMENTAL_OBSERVABILITY_ONLY_NOT_UNIVERSAL_RULES','minimum_street_valid_year_peers':MIN_STREET_PEERS,
        'subject_year_percentile_at_or_below':OLD_QUANTILE,'minimum_gap_below_street_median_years':MIN_YEAR_GAP,
        'minimum_materially_newer_street_peers':MIN_NEWER_PEERS,'materially_newer_definition_year_gap':MIN_YEAR_GAP},
      'candidates':cand[:60], 'candidate_payload':{'total':len(cand),'returned':min(60,len(cand)),'complete':len(cand)<=60,'display_policy':'NOVELTY_FIRST_DIAGNOSTIC_NOT_OPERATOR_RANKING'},
      'interpretation_policy':{'data_serves_decision':True,'year_built_not_condition':True,'age_mismatch_not_obsolescence_proof':True,
        'age_mismatch_not_seller_intent':True,'street_context_not_true_adjacency':True,'no_entitlement_or_buildability_inference':True,
        'no_generic_enrichment':True,'unknown_valid_state':True,'promote_only_if_meaningful_novel_discovery':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'v19v_touched':False,
        'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'MEASURE NOVEL PROPERTY DISCOVERY. IF MEANINGFUL NOVEL CASES EXIST, INTEGRATE AGE_MISMATCH AS AN INDEPENDENT WHY_FOUND RAIL; IF NOT, KILL THIS RAIL AND MOVE TO A DIFFERENT OPPORTUNITY FAMILY WITHOUT ADDING DATA.'}
if __name__=='__main__':print(json.dumps(build_find12(),indent=2,sort_keys=True))
