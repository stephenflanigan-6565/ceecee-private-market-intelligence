#!/usr/bin/env python3
import os, json, math, statistics
from collections import defaultdict
from datetime import datetime, timezone
from targeted_property_assessment_lookup_v1 import build_targeted_property_assessment_lookup_v1, ALIASES, CORE_FAMILIES, MARKET, TARGET_PARCEL, _payload, _flat, _pick, _num

VERSION='PROPERTY_FORM_PEER_CONTEXT_V1'

def _med(xs): return statistics.median(xs) if xs else None

def _pct(xs,x):
    if not xs or x is None: return None
    return (sum(v<x for v in xs)+0.5*sum(v==x for v in xs))/len(xs)

def _ratio(m):
    t,_=_pick(m,ALIASES['assessed_total']); l,_=_pick(m,ALIASES['assessed_land'])
    t=_num(t); l=_num(l)
    if t is None or l in (None,0) or t<l: return None
    return (t-l)/l

def build_property_form_peer_context_v1():
    prior=build_targeted_property_assessment_lookup_v1()
    if prior.get('status')!='ok': return {'status':'upstream_not_ok','version':VERSION,'upstream':prior,'database_writes':0}
    target=prior['verified_property_assessment_facts']; tr=target.get('improvement_to_land_ratio')
    import psycopg
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor()
        cur.execute('''SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
                       ORDER BY parcel_id,evidence_family,evidence_key''',(MARKET,list(CORE_FAMILIES)))
        rows=cur.fetchall()
    finally: conn.close()
    parcels=defaultdict(dict)
    for pid,fam,pj in rows:
        parcels[pid].setdefault(fam,{})
        for k,v in _flat(_payload(pj)).items():
            if v not in (None,'') and k not in parcels[pid][fam]: parcels[pid][fam][k]=v
    records=[]
    for pid,fams in parcels.items():
        m={}
        for fam in CORE_FAMILIES: m.update(fams.get(fam,{}))
        vals={}
        for name in ('address','property_class','acres','living_sqft','year_built','assessed_total','assessed_land'):
            raw,_=_pick(m,ALIASES[name]); vals[name]=_num(raw) if name in {'acres','living_sqft','year_built','assessed_total','assessed_land'} else (str(raw).strip() if raw not in (None,'') else None)
        vals['parcel_id']=pid; vals['ratio']=_ratio(m)
        if vals['ratio'] is not None: records.append(vals)
    tc=str(target.get('property_class')); ta=target.get('acres'); ts=target.get('living_sqft'); ty=target.get('year_built')
    def same_class(r): return str(r.get('property_class'))==tc
    def dune(r): return same_class(r) and 'DUNE RD' in str(r.get('address') or '').upper()
    def small_lot(r): return dune(r) and ta not in (None,0) and r.get('acres') is not None and abs(r['acres']-ta)<=max(.03,ta*.30)
    def physical(r):
        if not small_lot(r): return False
        sq_ok=ts in (None,0) or r.get('living_sqft') is None or abs(r['living_sqft']-ts)<=max(250,ts*.35)
        yr_ok=ty is None or r.get('year_built') is None or abs(r['year_built']-ty)<=20
        return sq_ok and yr_ok
    groups={'SAME_CLASS':[r for r in records if same_class(r)],'SAME_CLASS_DUNE_RD':[r for r in records if dune(r)],'DUNE_SMALL_LOT_CONTEXT':[r for r in records if small_lot(r)],'DUNE_SMALL_LOT_PHYSICAL_CONTEXT':[r for r in records if physical(r)]}
    diagnostics={}
    for name,g in groups.items():
        xs=[r['ratio'] for r in g]
        diagnostics[name]={'peer_count':len(xs),'median_improvement_to_land_ratio':round(_med(xs),6) if xs else None,'target_percentile':round(_pct(xs,tr),6) if xs else None,'target_ratio':round(tr,6) if tr is not None else None}
    strongest=diagnostics['DUNE_SMALL_LOT_PHYSICAL_CONTEXT']
    enough=strongest['peer_count']>=5
    survives=enough and strongest['target_percentile'] is not None and strongest['target_percentile']>=.90
    if not enough: state='CONTEXTUAL_PEER_GROUP_TOO_SMALL_KEEP_CAUSE_UNRESOLVED'
    elif survives: state='ANOMALY_SURVIVES_PROPERTY_FORM_AWARE_PEER_CONTEXT'
    else: state='ANOMALY_WEAKENS_UNDER_PROPERTY_FORM_AWARE_PEER_CONTEXT'
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_PROPERTY_FORM_AWARE_PEER_TEST','generated_at':datetime.now(timezone.utc).isoformat(),
      'target':{'parcel_id':TARGET_PARCEL,'property_address':target.get('address'),'property_class':target.get('property_class')},
      'human_local_context_hypothesis':'TARGET_APPEARS_TO_BELONG_TO_AN_UNUSUAL_CLUSTERED_DUNE_ROAD_PROPERTY_FORM; EXACT_LEGAL_FORM_NOT_ASSERTED',
      'external_context_already_established':{
        'authoritative_roll_confirms_individual_assessment_parcel':True,
        'stored_full_market_value_zero_is_ingestion_gap_not_real_zero':True,
        'legal_property_form_not_yet_verified':True
      },
      'peer_context_diagnostics':diagnostics,
      'resolution':{'state':state,'survives_contextual_peer_test':survives if enough else None,'minimum_contextual_peer_count':5,
                    'why_pmi_found_it':'LAND_VERSUS_IMPROVEMENT_ASSESSMENT_RELATIONSHIP_REMAINS_UNUSUAL' if survives else 'ASSESSMENT_ANOMALY_REQUIRES_PROPERTY_FORM_CONTEXT_BEFORE_OPPORTUNITY_USE',
                    'seller_intent':'UNKNOWN'},
      'policy':{'human_local_knowledge_is_hypothesis_until_verified':True,'property_form_before_peer_selection':True,'class_code_alone_not_sufficient_when_cluster_context_exists':True,'missing_information_nonblocking':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'IF_CONTEXTUAL_PEERS_ARE_SUFFICIENT_AND_ANOMALY_SURVIVES, RESOLVE_EXACT_PROPERTY_FORM_OR_ASSESSMENT_CLASS_SEMANTICS_BEFORE_SCALING_TO_OTHER_CASES; IF_IT_WEAKENS, DOWNGRADE_THIS_CASE_WITHOUT_KILLING_OTHER_ROUTES'
    }
