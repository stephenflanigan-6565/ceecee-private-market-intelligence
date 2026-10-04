#!/usr/bin/env python3
import os,re,json
from collections import defaultdict,Counter
from datetime import datetime,timezone
from find13 import build_find13
from find2 import _payload,_flat,_pick,_num,ALIASES

VERSION='FIND14'; MARKET='WESTHAMPTON_BEACH_NY'
MIN_PEERS=8; RECENT_YEAR=2015; MIN_RECENT=3; MIN_RECENT_SHARE=.25; SUBJECT_BEFORE=2000
SUFFIX={'ROAD':'RD','AVENUE':'AVE','STREET':'ST','LANE':'LN','DRIVE':'DR','COURT':'CT','HIGHWAY':'HWY','BOULEVARD':'BLVD','PLACE':'PL','TERRACE':'TER'}
def _street(addr):
    if not addr:return None
    s=re.sub(r'[^A-Z0-9 ]+',' ',str(addr).upper()).strip(); parts=s.split()
    if parts and re.match(r'^\d+[A-Z]?$',parts[0]):parts=parts[1:]
    if parts and parts[-1] in SUFFIX:parts[-1]=SUFFIX[parts[-1]]
    return ' '.join(parts) or None

def build_find14():
    import psycopg
    f13=build_find13(include_all_profiles=True); covered={str(p.get('parcel_id')) for p in f13.get('profiles',[])}
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
    props=[]
    for pid,m in by.items():
        addr=_pick(m,ALIASES['address']); y=_num(_pick(m,ALIASES['year_built']))
        if y is None or not (1600<=y<=datetime.now().year+1):continue
        st=_street(addr)
        if st:props.append({'parcel_id':pid,'property_address':str(addr).strip() if addr else None,'street_context':st,'year_built':int(y)})
    streets=defaultdict(list)
    for p in props:streets[p['street_context']].append(p)
    cand=[];ex=Counter()
    for p in props:
        peers=[x for x in streets[p['street_context']] if x['parcel_id']!=p['parcel_id']]
        if len(peers)<MIN_PEERS:ex['STREET_VALID_YEAR_PEERS_LT_8']+=1;continue
        recent=[x for x in peers if x['year_built']>=RECENT_YEAR]
        share=len(recent)/len(peers)
        if p['year_built']>=SUBJECT_BEFORE:continue
        if len(recent)<MIN_RECENT or share<MIN_RECENT_SHARE:continue
        cand.append({'parcel_id':p['parcel_id'],'property_address':p['property_address'],'street_context':p['street_context'],'subject_year_built':p['year_built'],
          'street_valid_year_peer_count':len(peers),'recent_2015_plus_peer_count':len(recent),'recent_2015_plus_peer_share':round(share,6),
          'example_recent_redevelopment_properties':[{'parcel_id':x['parcel_id'],'property_address':x['property_address'],'year_built':x['year_built']} for x in sorted(recent,key=lambda z:z['year_built'],reverse=True)[:5]],
          'observed_relationship':'OLDER_EXISTING_IMPROVEMENT_WITHIN_MICRO_CORRIDOR_SHOWING_CONCENTRATED_RECENT_REBUILD_ACTIVITY',
          'hypothesis':'MICRO_CORRIDOR_REDEVELOPMENT_HALO_OR_POTENTIAL_HOLDOUT_CONTEXT','existing_find13_coverage':p['parcel_id'] in covered,
          'novel_to_find13':p['parcel_id'] not in covered,'state':'OBSERVED_DISCOVERY_HYPOTHESIS','seller_intent':'UNKNOWN','contact_authorized':False,
          'next_question':'Does existing property/land evidence show that this apparently static property is economically or physically mismatched with the observed redevelopment halo?',
          'limits':['SAME_STREET_CONTEXT_IS_NOT_TRUE_ADJACENCY','YEAR_BUILT_DOES_NOT_PROVE_TEARDOWN_OR_REDEVELOPMENT','RECENT_CONSTRUCTION_CONTEXT_DOES_NOT_PROVE_SUBJECT_BUILDABILITY','NO_SELLER_INTENT_INFERENCE']})
    cand.sort(key=lambda r:(not r['novel_to_find13'],-r['recent_2015_plus_peer_share'],-r['recent_2015_plus_peer_count'],r['parcel_id']))
    novel=sum(1 for c in cand if c['novel_to_find13'])
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_INDEPENDENT_REDEVELOPMENT_HALO_HOLDOUT_DISCOVERY_EXPERIMENT','generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_OU_023_REDEVELOPMENT_HALO_AND_OU_024_NEW_CONSTRUCTION_ENCIRCLEMENT_USING_EXISTING_EVIDENCE_ONLY',
      'summary':{'working_valid_year_street_records':len(props),'street_contexts':len(streets),'observed_redevelopment_halo_candidates':len(cand),'novel_to_find13':novel,'already_covered_by_find13':len(cand)-novel,'exclusions':dict(ex)},
      'research_thresholds':{'status':'EXPERIMENTAL_WHB_OBSERVABILITY_ONLY_NOT_UNIVERSAL_RULES','minimum_valid_year_peers':MIN_PEERS,'recent_construction_year_at_or_after':RECENT_YEAR,'minimum_recent_peers':MIN_RECENT,'minimum_recent_peer_share':MIN_RECENT_SHARE,'subject_year_before':SUBJECT_BEFORE},
      'candidates':cand[:80],'candidate_payload':{'total':len(cand),'returned':min(80,len(cand)),'complete':len(cand)<=80,'display_policy':'NOVELTY_FIRST_DIAGNOSTIC_NOT_OPERATOR_RANKING'},
      'interpretation_policy':{'data_serves_decision':True,'redevelopment_halo_not_entitlement':True,'redevelopment_halo_not_seller_intent':True,'same_street_not_true_adjacency':True,'no_generic_enrichment':True,'unknown_valid_state':True,'promote_only_if_meaningful_independent_or_novel_discovery':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'MEASURE NOVELTY AND INDEPENDENCE VERSUS FIND13. PROMOTE ONLY IF THIS SURROUNDING_CHANGE_RAIL ADDS MEANINGFUL DISCOVERY OR DISTINCT CORROBORATION; OTHERWISE KILL IT WITHOUT ADDING DATA.'}
if __name__=='__main__':print(json.dumps(build_find14(),indent=2,sort_keys=True))
