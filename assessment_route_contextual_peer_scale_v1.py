#!/usr/bin/env python3
import os, json, math, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from assessment_improvement_fact_resolution_v1 import build_assessment_improvement_fact_resolution_v1
from targeted_property_assessment_lookup_v1 import ALIASES, CORE_FAMILIES, MARKET, _payload, _flat, _pick, _num

VERSION='ASSESSMENT_ROUTE_CONTEXTUAL_PEER_SCALE_V1'
TARGET_ROUTE='VERIFY_IMPROVEMENT_AND_ASSESSMENT_SEMANTICS'
MIN_PEERS=5
SURVIVE_PERCENTILE=.90

def _pct(xs,x):
    if not xs or x is None: return None
    return (sum(v<x for v in xs)+0.5*sum(v==x for v in xs))/len(xs)

def _med(xs): return statistics.median(xs) if xs else None

def _ratio(r):
    t=r.get('assessed_total'); l=r.get('assessed_land')
    if t is None or l in (None,0) or t<l: return None
    return (t-l)/l

def _num_or_none(v): return _num(v)

def build_assessment_route_contextual_peer_scale_v1():
    checkpoint=build_assessment_improvement_fact_resolution_v1()
    targets=checkpoint.get('resolved_cases') or []
    if checkpoint.get('status')!='ok' or len(targets)!=24:
        return {'status':'upstream_not_ok','version':VERSION,'upstream_status':checkpoint.get('status'),'target_count':len(targets),'database_writes':0}

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
    by_id={}
    for pid,fams in parcels.items():
        m={}
        for fam in CORE_FAMILIES: m.update(fams.get(fam,{}))
        r={'parcel_id':pid}
        for name in ('address','property_class','acres','living_sqft','year_built','assessed_total','assessed_land'):
            raw,_=_pick(m,ALIASES[name])
            r[name]=_num_or_none(raw) if name in {'acres','living_sqft','year_built','assessed_total','assessed_land'} else (str(raw).strip() if raw not in (None,'') else None)
        r['ratio']=_ratio(r)
        records.append(r); by_id[pid]=r

    results=[]
    for c in targets:
        pid=c.get('parcel_id'); t=by_id.get(pid)
        if not t or t.get('ratio') is None:
            results.append({'parcel_id':pid,'property_address':c.get('property_address'),'state':'INSUFFICIENT_TARGET_COMPONENTS','seller_intent':'UNKNOWN','contact_authorized':False})
            continue
        pc=str(t.get('property_class') or '')
        addr=str(t.get('address') or '').upper()
        street=' '.join(addr.split()[-2:]) if len(addr.split())>=2 else addr
        ta=t.get('acres'); ts=t.get('living_sqft'); ty=t.get('year_built')
        same=[r for r in records if r.get('ratio') is not None and str(r.get('property_class') or '')==pc]
        # Contextual physical peers: same source class, then constrain by lot/size/year when target facts exist.
        physical=[]
        for r in same:
            ac=r.get('acres'); sq=r.get('living_sqft'); yr=r.get('year_built')
            acre_ok=ta in (None,0) or ac is None or abs(ac-ta)<=max(.10,ta*.35)
            sq_ok=ts in (None,0) or sq is None or abs(sq-ts)<=max(350,ts*.35)
            yr_ok=ty is None or yr is None or abs(yr-ty)<=20
            if acre_ok and sq_ok and yr_ok: physical.append(r)
        same_street=[r for r in same if street and street in str(r.get('address') or '').upper()]
        # Prefer contextual physical peers when sufficient; otherwise same-class remains the fallback, explicitly marked.
        chosen=physical if len(physical)>=MIN_PEERS else same
        basis='SAME_CLASS_PHYSICAL_CONTEXT' if len(physical)>=MIN_PEERS else 'SAME_CLASS_FALLBACK_INSUFFICIENT_PHYSICAL_CONTEXT'
        xs=[r['ratio'] for r in chosen]
        pct=_pct(xs,t['ratio'])
        survives=len(xs)>=MIN_PEERS and pct is not None and pct>=SURVIVE_PERCENTILE
        state='SURVIVES_CONTEXTUAL_PEER_KILL_TEST' if survives else ('WEAKENS_UNDER_CONTEXTUAL_PEERS' if len(xs)>=MIN_PEERS else 'INSUFFICIENT_CONTEXTUAL_PEERS_KEEP_UNRESOLVED')
        class_semantics='SEASONAL_RESIDENCE' if pc=='260' else 'SOURCE_CLASS_CODE_MEANING_NOT_ASSERTED'
        results.append({
          'parcel_id':pid,'property_address':t.get('address') or c.get('property_address'),'property_class':pc,
          'class_semantics':class_semantics,'target_improvement_to_land_ratio':round(t['ratio'],6),
          'peer_basis_used':basis,'peer_count':len(xs),'peer_median_ratio':round(_med(xs),6) if xs else None,
          'target_percentile':round(pct,6) if pct is not None else None,
          'diagnostic_counts':{'same_class':len(same),'same_class_physical_context':len(physical),'same_class_same_street':len(same_street)},
          'state':state,'survives_kill_test':survives if len(xs)>=MIN_PEERS else None,
          'why_pmi_found_it':'LAND_VERSUS_IMPROVEMENT_ASSESSMENT_RELATIONSHIP_REMAINS_UNUSUAL_AFTER_CONTEXTUAL_PEER_TEST' if survives else None,
          'next_research_need':'TARGETED_AUTHORITATIVE_PROPERTY_OR_ASSESSMENT_FACT_ONLY_IF_CASE_SURVIVES' if survives else ('DO_NOT_SPEND_EXTERNAL_LOOKUP_ON_THIS_ROUTE_YET' if state=='WEAKENS_UNDER_CONTEXTUAL_PEERS' else 'RESOLVE_PEER_CONTEXT_BEFORE_EXTERNAL_LOOKUP'),
          'seller_intent':'UNKNOWN','contact_authorized':False
        })

    counts=Counter(x['state'] for x in results)
    survivors=[x for x in results if x.get('survives_kill_test') is True]
    weakened=[x for x in results if x.get('state')=='WEAKENS_UNDER_CONTEXTUAL_PEERS']
    unresolved=[x for x in results if x.get('survives_kill_test') is None]
    ids=[x.get('parcel_id') for x in results if x.get('parcel_id')]
    reconciled=len(results)==24 and len(set(ids))==24
    return {
      'status':'ok' if reconciled else 'reconciliation_failed','version':VERSION,'mode':'READ_ONLY_SCALED_CONTEXTUAL_PEER_KILL_TEST',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'source_checkpoint':{'version':checkpoint.get('version'),'target_route':TARGET_ROUTE,'expected_cases':24},
      'class_semantics_contract':{'260':'SEASONAL_RESIDENCE','all_other_codes':'SOURCE_CLASSIFICATION_ONLY_UNTIL_SEMANTICALLY_RESOLVED'},
      'method':{'minimum_peer_count':MIN_PEERS,'survival_percentile_threshold':SURVIVE_PERCENTILE,'contextual_peer_rule':'SAME_CLASS + LOT_WITHIN_MAX_0.10_ACRE_OR_35_PERCENT + LIVING_SQFT_WITHIN_MAX_350_OR_35_PERCENT + YEAR_BUILT_WITHIN_20_WHEN_AVAILABLE','fallback':'SAME_CLASS_ONLY_IF_CONTEXTUAL_PHYSICAL_GROUP_HAS_FEWER_THAN_5'},
      'summary':{'cases_tested':len(results),'states':dict(counts),'survivors':len(survivors),'weakened':len(weakened),'unresolved_peer_context':len(unresolved),'external_lookups_used':0},
      'reconciliation':{'expected':24,'received':len(results),'unique_parcels':len(set(ids)),'all_cases_accounted_for':reconciled},
      'cases':results,
      'decision':{'external_lookup_policy':'SPEND_EXTERNAL_RESEARCH_ONLY_ON_SURVIVORS_AFTER_THIS_KILL_TEST','bulk_manual_review':False,'seller_intent':'UNKNOWN','contact_authorized':False},
      'policy':{'class_semantics_before_interpretation':True,'contextual_peers_before_external_lookup':True,'missing_information_nonblocking':True,'data_quality_is_not_opportunity_evidence':True,'full_market_value_zero_field_prohibited':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'REVIEW_SURVIVOR_COUNT; THEN RESOLVE_HIGHEST_INFORMATION_VALUE_CLASS_OR_PROPERTY_FACT_SHARED_BY_SURVIVORS_BEFORE_ANY_BULK_EXTERNAL_LOOKUPS'
    }
