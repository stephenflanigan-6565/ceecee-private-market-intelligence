#!/usr/bin/env python3
import os,re
from collections import defaultdict,Counter
from datetime import datetime,timezone
from find2 import _payload,_flat,_pick,_num,_pct,_med,ALIASES
from find15 import _expanded_discovered_universe

VERSION='FIND16'; MARKET='WESTHAMPTON_BEACH_NY'
MIN_CLASS_PEERS=20; MIN_STREET_PEERS=8
LAND_SHARE_PCTL=.75; IMPROVEMENT_TO_LAND_PCTL=.25; LIVING_SQFT_PCTL=.35
RECENT_YEAR=2015; MIN_RECENT_PEERS=2; MIN_RECENT_SHARE=.20; SUBJECT_BEFORE=2000
SUFFIX={'ROAD':'RD','AVENUE':'AVE','STREET':'ST','LANE':'LN','DRIVE':'DR','COURT':'CT','HIGHWAY':'HWY','BOULEVARD':'BLVD','PLACE':'PL','TERRACE':'TER'}

def _street(addr):
    if not addr:return None
    s=re.sub(r'[^A-Z0-9 ]+',' ',str(addr).upper()).strip(); parts=s.split()
    if parts and re.match(r'^\d+[A-Z]?$',parts[0]):parts=parts[1:]
    if parts and parts[-1] in SUFFIX:parts[-1]=SUFFIX[parts[-1]]
    return ' '.join(parts) or None

def build_find16():
    import psycopg
    _,_,existing,_=_expanded_discovered_universe(); existing_ids=set(existing)
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor();cur.execute("""SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
          WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
          ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,['PROPERTY_CONTEXT','ASSESSMENT_CONTEXT']))
        rows=cur.fetchall()
    finally:conn.close()
    by=defaultdict(dict)
    for pid,fam,pj in rows:
        for k,v in _flat(_payload(pj)).items():
            if k not in by[str(pid)] and v not in (None,''):by[str(pid)][k]=v
    recs=[]
    for pid,m in by.items():
        r={'parcel_id':pid}
        for k,aa in ALIASES.items():
            v=_pick(m,aa);r[k]=_num(v) if k in ('acres','assessment_total','land_assessment','year_built','living_sqft') else (str(v).strip() if v not in (None,'') else None)
        t,l=r['assessment_total'],r['land_assessment']
        r['improvement_assessment']=t-l if t is not None and l is not None and t>=l else None
        r['improvement_to_land']=r['improvement_assessment']/l if l not in (None,0) and r['improvement_assessment'] is not None else None
        r['land_share']=l/t if t not in (None,0) and l is not None else None
        r['street_context']=_street(r['address'])
        recs.append(r)
    classes=defaultdict(list); streets=defaultdict(list)
    for r in recs:
        if r['property_class']:classes[r['property_class']].append(r)
        if r['street_context'] and r['year_built'] and 1600<=r['year_built']<=datetime.now().year+1:streets[r['street_context']].append(r)
    cand=[];ex=Counter()
    for r in recs:
        peers=classes.get(r['property_class'],[])
        if len(peers)<MIN_CLASS_PEERS:ex['CLASS_PEER_GROUP_LT_20']+=1;continue
        if r['land_share'] is None or r['improvement_to_land'] is None or r['year_built'] is None or not r['street_context']:
            ex['MISSING_CORE_PROPERTY_ECONOMIC_OR_MICRO_CONTEXT']+=1;continue
        if r['year_built']>=SUBJECT_BEFORE:continue
        ratio=[p['improvement_to_land'] for p in peers if p['improvement_to_land'] is not None]
        share=[p['land_share'] for p in peers if p['land_share'] is not None]
        sqft=[p['living_sqft'] for p in peers if p['living_sqft'] is not None and p['living_sqft']>0]
        rp=_pct(ratio,r['improvement_to_land']); sp=_pct(share,r['land_share']); qp=_pct(sqft,r['living_sqft']) if r['living_sqft'] and r['living_sqft']>0 else None
        # Part 1: site carries unusually high economic weight, but gate is intentionally broader than FIND2.
        if sp is None or sp<LAND_SHARE_PCTL:continue
        # Part 2: existing improvement is economically or physically light relative to compatible class peers.
        light_econ=rp is not None and rp<=IMPROVEMENT_TO_LAND_PCTL
        light_phys=qp is not None and qp<=LIVING_SQFT_PCTL
        if not (light_econ or light_phys):continue
        street_peers=[x for x in streets[r['street_context']] if x['parcel_id']!=r['parcel_id']]
        if len(street_peers)<MIN_STREET_PEERS:ex['STREET_VALID_YEAR_PEERS_LT_8']+=1;continue
        recent=[x for x in street_peers if x['year_built']>=RECENT_YEAR]
        recent_share=len(recent)/len(street_peers)
        # Part 3: observed local replacement/reinvestment activity must actually exist.
        if len(recent)<MIN_RECENT_PEERS or recent_share<MIN_RECENT_SHARE:continue
        novel=r['parcel_id'] not in existing_ids
        mechanisms=['LAND_CARRIES_HIGH_RELATIVE_ECONOMIC_WEIGHT']
        if light_econ:mechanisms.append('IMPROVEMENT_ECONOMIC_WEIGHT_LIGHT_RELATIVE_TO_CLASS')
        if light_phys:mechanisms.append('IMPROVEMENT_PHYSICAL_SIZE_LIGHT_RELATIVE_TO_CLASS')
        mechanisms.append('MICRO_CORRIDOR_SHOWS_OBSERVED_RECENT_REINVESTMENT')
        cand.append({
          'parcel_id':r['parcel_id'],'property_address':r['address'],'property_class':r['property_class'],
          'subject_year_built':int(r['year_built']),'street_context':r['street_context'],
          'actual_values':{'land_assessment':r['land_assessment'],'improvement_assessment':r['improvement_assessment'],'assessment_total':r['assessment_total'],'land_share_of_assessment':round(r['land_share'],6),'improvement_to_land_ratio':round(r['improvement_to_land'],6),'living_sqft':r['living_sqft'],'acres':r['acres']},
          'peer_context':{'same_class_peer_count':len(peers),'land_share_percentile':round(sp,6),'improvement_to_land_percentile':round(rp,6) if rp is not None else None,'living_sqft_percentile':round(qp,6) if qp is not None else None,'improvement_to_land_peer_median':round(_med(ratio),6) if ratio else None},
          'replacement_context':{'street_valid_year_peer_count':len(street_peers),'recent_2015_plus_peer_count':len(recent),'recent_2015_plus_peer_share':round(recent_share,6),'example_recent_properties':[{'parcel_id':x['parcel_id'],'property_address':x['address'],'year_built':int(x['year_built'])} for x in sorted(recent,key=lambda z:z['year_built'],reverse=True)[:5]]},
          'observed_mechanisms':mechanisms,
          'hypothesis':'LAND_LED_REPLACEMENT_OR_TEARDOWN_REBUILD_ECONOMIC_MISMATCH_REQUIRES_TARGETED_KILL_TEST',
          'existing_discovery_universe_coverage':not novel,'novel_to_existing_226_property_universe':novel,
          'state':'OBSERVED_DISCOVERY_HYPOTHESIS','seller_intent':'UNKNOWN','contact_authorized':False,
          'next_question':'What single site, lawful-use, improvement-condition, or replacement-economics fact would most strongly destroy or support the land-led replacement thesis?',
          'limits':['ASSESSMENT_RELATIONSHIP_IS_NOT_MARKET_PRICE','YEAR_BUILT_IS_NOT_CONDITION','SAME_STREET_IS_MICRO_CORRIDOR_PROXY_NOT_TRUE_ADJACENCY','REINVESTMENT_CONTEXT_DOES_NOT_PROVE_SUBJECT_BUILDABILITY','NO_DEMOLITION_OR_REBUILD_FEASIBILITY_INFERENCE','NO_SELLER_INTENT_INFERENCE']
        })
    cand.sort(key=lambda x:(not x['novel_to_existing_226_property_universe'],-x['replacement_context']['recent_2015_plus_peer_share'],-x['peer_context']['land_share_percentile'],x['parcel_id']))
    novel=sum(1 for x in cand if x['novel_to_existing_226_property_universe'])
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_INDEPENDENT_LAND_LED_REPLACEMENT_ECONOMICS_DISCOVERY_EXPERIMENT','generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_OU_002_OBSOLETE_IMPROVEMENT_ON_VALUABLE_LAND_AND_OU_003_TEARDOWN_REBUILD_ECONOMICS_AS_A_COMBINATION_MECHANISM_DISTINCT_FROM_EXISTING_SINGLE_RAILS',
      'architecture':{'existing_discovery_universe_properties':len(existing_ids),'requires_three_part_mechanism':True,'part_1':'RELATIVE_LAND_ECONOMIC_WEIGHT','part_2':'LIGHT_EXISTING_IMPROVEMENT_RELATIVE_TO_COMPATIBLE_CLASS','part_3':'OBSERVED_LOCAL_REINVESTMENT_CONTEXT','not_merely_old_house':True,'not_merely_land_dominance':True,'not_merely_redevelopment_halo':True},
      'summary':{'working_property_universe':len(recs),'observed_replacement_economics_candidates':len(cand),'novel_to_existing_226_property_universe':novel,'already_discovered_but_distinctly_corroborated':len(cand)-novel,'exclusions':dict(ex)},
      'research_thresholds':{'status':'EXPERIMENTAL_WHB_OBSERVABILITY_ONLY_NOT_UNIVERSAL_TEARDOWN_RULES','minimum_same_class_peers':MIN_CLASS_PEERS,'minimum_street_valid_year_peers':MIN_STREET_PEERS,'minimum_land_share_percentile':LAND_SHARE_PCTL,'maximum_improvement_to_land_percentile':IMPROVEMENT_TO_LAND_PCTL,'maximum_living_sqft_percentile_as_alternate_light_improvement_evidence':LIVING_SQFT_PCTL,'subject_year_before':SUBJECT_BEFORE,'recent_construction_year_at_or_after':RECENT_YEAR,'minimum_recent_street_peers':MIN_RECENT_PEERS,'minimum_recent_street_peer_share':MIN_RECENT_SHARE},
      'candidates':cand[:80],'candidate_payload':{'total':len(cand),'returned':min(80,len(cand)),'complete':len(cand)<=80,'display_policy':'NOVELTY_FIRST_DIAGNOSTIC_NOT_OPERATOR_RANKING'},
      'interpretation_policy':{'data_serves_decision':True,'combination_reasoning_required':True,'assessment_not_market_price':True,'age_not_condition':True,'replacement_hypothesis_not_buildability':True,'replacement_hypothesis_not_seller_intent':True,'no_generic_enrichment':True,'unknown_valid_state':True,'route_kill_never_equals_property_kill':True,'promote_only_if_mechanism_is_distinct_and_information_bearing':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'MEASURE NOVEL DISCOVERY AND DISTINCT CORROBORATION VERSUS THE CURRENT 226_PROPERTY UNIVERSE. PROMOTE ONLY IF THE THREE_PART_REPLACEMENT_MECHANISM ADDS INFORMATION BEYOND LAND, AGE, OR HALO RAILS ALONE; OTHERWISE KILL IT WITHOUT ADDING DATA.'}

if __name__=='__main__':
    import json;print(json.dumps(build_find16(),indent=2,sort_keys=True))
