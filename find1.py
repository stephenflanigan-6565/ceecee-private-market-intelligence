#!/usr/bin/env python3
import os, json
from collections import Counter, defaultdict
from datetime import datetime, timezone

VERSION='FIND1'
MARKET='WESTHAMPTON_BEACH_NY'

OWNER_ALIASES=('owner_name','owner','ownername','current_owner','owner_1','owner1','name')

def _payload(v):
    if isinstance(v,dict): return v
    try:
        x=json.loads(v) if v else {}
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}

def _flat(d):
    out={}
    def walk(x):
        if not isinstance(x,dict): return
        for k,v in x.items():
            key=str(k).lower().strip()
            if isinstance(v,dict): walk(v)
            elif key not in out and v not in (None,''): out[key]=v
    walk(d); return out

def _owner_value(payload):
    f=_flat(payload)
    for k in OWNER_ALIASES:
        if f.get(k) not in (None,''):
            return str(f[k]).strip()
    return None

def _ownership_snapshot(parcel_ids):
    if not parcel_ids: return {}
    import psycopg
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor()
        cur.execute('''SELECT parcel_id,payload_json FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1
                         AND evidence_family='OWNERSHIP' AND parcel_id=ANY(%s)
                       ORDER BY parcel_id,evidence_key''',(MARKET,list(parcel_ids)))
        rows=cur.fetchall()
    finally:
        conn.close()
    by=defaultdict(list)
    for pid,pj in rows:
        name=_owner_value(_payload(pj))
        if name and name not in by[pid]: by[pid].append(name)
    return dict(by)

def build_find1():
    from property_research_router_v1 import build_property_research_router_v1
    from class_210_causal_scale_v1 import build_class_210_causal_scale_v1

    routed=build_property_research_router_v1()
    c210=build_class_210_causal_scale_v1()
    cases=routed.get('routed_cases') or []
    c210_ids={x.get('parcel_id') for x in (c210.get('cases') or []) if x.get('parcel_id')}
    ids=[x.get('parcel_id') for x in cases if x.get('parcel_id')]
    owners=_ownership_snapshot(ids)

    profiles=[]
    route_states=Counter(); current_states=Counter()
    for c in cases:
        pid=c.get('parcel_id')
        discovery=[]
        # Preserve the original property-originated reason as history.
        assessment_closed = pid in c210_ids
        discovery.append({
          'route':'ASSESSMENT_PROPERTY_RELATIONSHIP',
          'noticed_because':c.get('opportunity_hypothesis') or 'PROPERTY_OR_LAND_RELATIONSHIP_REMAINS_UNEXPLAINED',
          'state':'EXPLAINED_ROUTE_CLOSED' if assessment_closed else 'ACTIVE_RESEARCH_ROUTE',
          'current_research_route':None if assessment_closed else c.get('research_route'),
          'next_question':None if assessment_closed else c.get('highest_information_value_question'),
          'does_not_equal_seller_intent':True
        })
        # Ownership is evidence/context, never an independent seller selector here.
        owner_names=owners.get(pid,[])
        discovery.append({
          'route':'OWNERSHIP_CONTEXT',
          'state':'CONTEXT_ONLY_NOT_QUALIFYING',
          'observed_owner_names':owner_names,
          'ownership_evidence_present':bool(owner_names),
          'does_not_equal_seller_intent':True
        })
        active=[x for x in discovery if x['state']=='ACTIVE_RESEARCH_ROUTE']
        closed=[x for x in discovery if x['state']=='EXPLAINED_ROUTE_CLOSED']
        unknowns=list(c.get('missing_context') or []) + list(c.get('data_quality_uncertainties') or [])
        current_state='RESEARCH_ACTIVE' if active else 'NO_ACTIVE_ROUTE_FROM_CURRENT_INTEGRATED_RAILS'
        current_states[current_state]+=1
        for x in discovery: route_states[x['state']]+=1
        profiles.append({
          'parcel_id':pid,
          'property_address':c.get('property_address'),
          'owner_identity':{'names':owner_names,'verification_state':'UNKNOWN' if not owner_names else 'UNVERIFIED_FROM_CURRENT_OWNERSHIP_MEMORY'},
          'why_pmi_noticed_it':discovery,
          'why_it_still_deserves_attention': [x['route'] for x in active],
          'explained_or_closed_routes':[x['route'] for x in closed],
          'contradictions_and_unknowns':unknowns,
          'current_find_state':current_state,
          'seller_intent':'UNKNOWN',
          'contact_authorized':False,
          'operator_contract':{'show_property':True,'show_owner_when_present':True,'explain_why_found':True,'score_exposed':False}
        })

    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_PROPERTY_CENTRIC_FIND_PROFILE',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'architecture':{
        'flow':['DISCOVERY_ROUTES','EVIDENCE_STACK','HYPOTHESES','CAUSAL_OR_CONTRADICTION_TESTS','PROPERTY_OPPORTUNITY_PROFILE','VERIFICATION_GATE'],
        'property_centric_not_detector_centric':True,
        'noticed_reason_preserved_after_route_close':True,
        'route_kill_never_equals_property_kill':True,
        'title_or_ownership_cannot_independently_qualify':True,
        'operator_output_not_seller_score':True
      },
      'source_checkpoints':{'research_router':routed.get('version'),'class_210_causal_population':c210.get('version'),'class_210_branch_status':'CLOSED_19_OF_19_FROM_VERIFIED_CLOSEOUT'},
      'summary':{
        'profiles_assembled':len(profiles),
        'class_210_closed_routes_integrated':sum(1 for p in profiles if 'ASSESSMENT_PROPERTY_RELATIONSHIP' in p['explained_or_closed_routes']),
        'profiles_with_active_current_route':sum(1 for p in profiles if p['current_find_state']=='RESEARCH_ACTIVE'),
        'profiles_with_no_active_route_from_current_integrated_rails':sum(1 for p in profiles if p['current_find_state']!='RESEARCH_ACTIVE'),
        'route_states':dict(route_states),'current_find_states':dict(current_states)
      },
      'profiles':profiles,
      'policy':{
        'one_fact_not_seller':True,'independent_routes_preserved':True,'explained_routes_retained_as_memory':True,
        'missing_information_nonblocking':True,'unknown_valid_state':True,'contradictions_first_class':True,
        'seller_intent_inferred':False,'marketing_execution':False,'score_or_rank_exposed':False
      },
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'USE PROPERTY-CENTRIC PROFILE AS FIND CHASSIS; ADD NEXT INDEPENDENT PROPERTY_OR_LAND_DISCOVERY MECHANISM WITHOUT REOPENING CLOSED ASSESSMENT ROUTES'
    }
