#!/usr/bin/env python3
import os,json,re
from collections import defaultdict,Counter
from datetime import datetime,timezone,date
from find13 import build_find13
from find14 import build_find14
from find1 import _payload,_flat,_owner_value

VERSION='FIND15'; MARKET='WESTHAMPTON_BEACH_NY'
RECENT_DAYS=730; DEEP_HISTORY_EVENTS=4
DATE_KEYS=('recording_date','event_date','instrument_date','doc_date','entry_date','date')
DOC_KEYS=('document_code','doc_code','doctype','document_type','type')

def _parse_date(v):
    if v in (None,''): return None
    s=str(v).strip()
    for x in (s[:10],s):
        try:return datetime.fromisoformat(x.replace('Z','+00:00')).date()
        except Exception:pass
    m=re.search(r'(20\d{2}|19\d{2})[-/](\d{1,2})[-/](\d{1,2})',s)
    if m:
        try:return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
        except Exception:return None
    return None

def _first(flat,keys):
    for k in keys:
        if flat.get(k) not in (None,''):return flat[k]
    return None

def _expanded_discovered_universe():
    f13=build_find13(include_all_profiles=True); f14=build_find14()
    by={str(p.get('parcel_id')):dict(p) for p in (f13.get('profiles') or [])}
    added=0
    for c in (f14.get('candidates') or []):
        pid=str(c.get('parcel_id'))
        if not pid or pid in by: continue
        by[pid]={'parcel_id':pid,'property_address':c.get('property_address'),'current_find_state':'RESEARCH_ACTIVE',
                 'seller_intent':'UNKNOWN','contact_authorized':False,
                 'why_pmi_noticed_it':[{'route':'REDEVELOPMENT_HALO_HOLDOUT_CONTEXT','state':'ACTIVE_RESEARCH_ROUTE',
                    'noticed_because':c.get('observed_relationship'),'hypothesis':c.get('hypothesis'),'does_not_equal_seller_intent':True}],
                 'why_it_still_deserves_attention':['REDEVELOPMENT_HALO_HOLDOUT_CONTEXT']}
        added+=1
    return f13,f14,by,added

def build_find15():
    import psycopg
    f13,f14,profiles,halo_added=_expanded_discovered_universe(); ids=list(profiles)
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor();cur.execute("""SELECT parcel_id,evidence_family,payload_json,evidence_key FROM evidence_ledger
          WHERE market_code=%s AND is_current=1 AND parcel_id=ANY(%s) AND evidence_family=ANY(%s)
          ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,ids,['OWNERSHIP','TRANSFER_TITLE']))
        rows=cur.fetchall()
    finally:conn.close()
    own=defaultdict(list); trans=defaultdict(list)
    for pid,fam,pj,ek in rows:
        pid=str(pid); p=_payload(pj); f=_flat(p)
        if fam=='OWNERSHIP':
            n=_owner_value(p)
            if n and n not in own[pid]:own[pid].append(n)
        elif fam=='TRANSFER_TITLE':
            d=_parse_date(_first(f,DATE_KEYS)); code=_first(f,DOC_KEYS)
            trans[pid].append({'date':d,'document_code':str(code).strip() if code not in (None,'') else None,'evidence_key':str(ek)})
    today=datetime.now(timezone.utc).date(); cases=[]; stats=Counter()
    for pid,p in profiles.items():
        events=trans.get(pid,[]); dated=[e for e in events if e['date']]
        latest=max((e['date'] for e in dated),default=None)
        days=(today-latest).days if latest else None
        recent=days is not None and 0<=days<=RECENT_DAYS
        names=own.get(pid,[])
        contexts=[]
        if recent:contexts.append('RECENT_REMEMBERED_TRANSFER_TITLE_EVENT_REQUIRES_CURRENT_CONTROL_INTERPRETATION')
        if len(events)>=DEEP_HISTORY_EVENTS:contexts.append('DEEP_TRANSFER_TITLE_MEMORY_PRESENT')
        if len(names)>=2:contexts.append('MULTIPLE_REMEMBERED_OWNER_NAME_FORMS_OR_PARTIES_PRESENT')
        if not contexts: continue
        # Context earns inclusion only because the property was independently discovered first.
        stats['properties_with_context']+=1
        if recent:stats['recent_event_context']+=1
        if len(events)>=DEEP_HISTORY_EVENTS:stats['deep_history_context']+=1
        if len(names)>=2:stats['multiple_owner_name_memory_context']+=1
        routes=[r.get('route') for r in (p.get('why_pmi_noticed_it') or []) if r.get('route') and r.get('route')!='OWNERSHIP_CONTEXT']
        cases.append({'parcel_id':pid,'property_address':p.get('property_address'),'independent_property_discovery_routes':routes,
          'ownership_memory':{'observed_owner_names':names,'verification_state':'UNVERIFIED_MEMORY_CONTEXT' if names else 'UNKNOWN'},
          'transfer_title_memory':{'event_count':len(events),'dated_event_count':len(dated),'latest_remembered_event_date':latest.isoformat() if latest else None,
             'days_since_latest_remembered_event':days,'latest_document_codes':sorted({e['document_code'] for e in events if e['document_code']})[:12]},
          'context_observations':contexts,'state':'SUPPORTING_CONTEXT_ONLY_NOT_DISCOVERY',
          'decision_impact':'MATERIAL_TO_CURRENT_CONTROL_VERIFICATION_BEFORE_RELATIONSHIP_WORK' if recent else 'NONBLOCKING_CONTEXT_UNLESS_PROPERTY_HYPOTHESIS_ADVANCES',
          'next_question':'If this property survives property-level investigation, who currently controls it and does the remembered chronology materially affect the relationship path?' if recent else 'No ownership research now; revisit control only if the independent property opportunity survives.',
          'seller_intent':'UNKNOWN','contact_authorized':False,
          'limits':['TITLE_OR_OWNERSHIP_CANNOT_INDEPENDENTLY_QUALIFY','DOCUMENT_CODE_DOES_NOT_PROVE_MOTIVE','OWNER_NAME_VARIANTS_DO_NOT_PROVE_LEGAL_COMPLEXITY','LONG_TENURE_NOT_INFERRED_FROM_INCOMPLETE_TITLE_MEMORY','CURRENT_OWNERSHIP_NOT_ASSUMED_FROM_HISTORICAL_MEMORY']})
    cases.sort(key=lambda x:(x['decision_impact']!='MATERIAL_TO_CURRENT_CONTROL_VERIFICATION_BEFORE_RELATIONSHIP_WORK',x['parcel_id']))
    material=sum(1 for x in cases if x['decision_impact'].startswith('MATERIAL'))
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_OWNERSHIP_CONTROL_CONTEXT_ON_INDEPENDENTLY_DISCOVERED_PROPERTIES_ONLY',
      'generated_at':datetime.now(timezone.utc).isoformat(),'purpose':'TEST_WHETHER_EXISTING_OWNERSHIP_AND_TRANSFER_TITLE_MEMORY_IMPROVES_NEXT_BEST_QUESTIONS_WITHOUT_EVER_CREATING_A_PROPERTY_OR_SELLER_OPPORTUNITY',
      'source_checkpoints':{'expanded_property_chassis':'FIND13_PLUS_15_NOVEL_FIND14_PROPERTIES','find13_profiles':len(f13.get('profiles') or []),'find14_novel_added':halo_added,'independently_discovered_properties_tested':len(profiles)},
      'summary':{'independently_discovered_properties_tested':len(profiles),'properties_with_any_supporting_ownership_control_context':len(cases),'properties_where_context_changes_verification_priority':material,**dict(stats)},
      'cases':cases[:80],'case_payload':{'total':len(cases),'returned':min(80,len(cases)),'complete':len(cases)<=80,'display_policy':'MATERIAL_DECISION_IMPACT_FIRST_DIAGNOSTIC_NOT_RANKING'},
      'research_thresholds':{'status':'EXPERIMENTAL_CONTEXT_OBSERVABILITY_ONLY','recent_remembered_event_days':RECENT_DAYS,'deep_transfer_title_memory_event_count':DEEP_HISTORY_EVENTS,'long_tenure_threshold':None,'reason_long_tenure_not_tested':'INCOMPLETE_TITLE_MEMORY_CANNOT_PROVE_CONTINUOUS_CONTROL_TENURE'},
      'interpretation_policy':{'property_must_be_independently_discovered_first':True,'ownership_context_never_adds_property_to_chassis':True,'title_never_independently_qualifies':True,'document_code_not_motive':True,'data_serves_decision':True,'unknown_valid_state':True,'no_generic_enrichment':True,'human_verification_only_when_material':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'PROMOTE ONLY IF OWNERSHIP_CONTROL_MEMORY MATERIALLY CHANGES NEXT_BEST_QUESTIONS ON ALREADY_DISCOVERED PROPERTIES. OTHERWISE KEEP IT AS PASSIVE MEMORY AND MOVE TO A NEW DISCOVERY FAMILY.'}
if __name__=='__main__':print(json.dumps(build_find15(),indent=2,sort_keys=True))
