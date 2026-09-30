#!/usr/bin/env python3
"""V16N — title/transfer event sequence & combination intelligence.
Read-only research layer over the proven Suffolk transfer history and V16M factual code map.
No seller intent, scoring, INVESTIGATE mutation, contact authorization, or database writes.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from db import connect, execute
from title_transfer_authority_v16m import SUFFOLK_CODES, FAMILY

VERSION='V16N'
MODE='READ_ONLY_EVENT_SEQUENCE_COMBINATION_INTELLIGENCE'
MARKET='WESTHAMPTON_BEACH_NY'
SOURCE='Suffolk TaxParcelTransferHistory'

def _rows(cur):
    cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def _date(v):
    if v in (None,''): return None
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    try: return date.fromisoformat(str(v)[:10])
    except Exception: return None

def _event_date(r):
    return _date(r.get('record_date')) or _date(r.get('document_date')) or _date(r.get('entry_date'))

def _code(r):
    c=str(r.get('document_code') or '').strip().upper()
    return c or '[MISSING]'

def _family(code):
    if code=='[MISSING]' or code not in SUFFOLK_CODES: return 'UNRESOLVED_SOURCE'
    return FAMILY.get(code,'UNRESOLVED_SOURCE')

def build_title_transfer_sequence_v16n():
    c=connect()
    try:
        members={str(r[0]) for r in execute(c,'SELECT parcel_id FROM property_market_membership WHERE market_code=?',(MARKET,)).fetchall()}
        raw=_rows(execute(c,'SELECT parcel_id, record_date, document_date, entry_date, document_number, document_code, history_sequence FROM transfers WHERE source=?',(SOURCE,)))
    finally:
        c.close()

    rows=[]
    for r in raw:
        pid=str(r.get('parcel_id'))
        if pid not in members: continue
        d=_event_date(r)
        if not d: continue
        code=_code(r)
        rows.append({**r,'parcel_id':pid,'event_date':d,'code':code,'family':_family(code)})

    by_property=defaultdict(list)
    for r in rows: by_property[r['parcel_id']].append(r)
    for events in by_property.values():
        events.sort(key=lambda x:(x['event_date'], str(x.get('history_sequence') or ''), str(x.get('document_number') or '')))

    today=date.today(); cut365=today-timedelta(days=365); cut1095=today-timedelta(days=1095)
    transitions=Counter(); code_transitions=Counter(); recent_family=Counter(); recent_code=Counter()
    pattern_counts=Counter(); pattern_properties=defaultdict(set); examples=defaultdict(list)

    def mark(pattern,pid,detail):
        pattern_counts[pattern]+=1; pattern_properties[pattern].add(pid)
        if len(examples[pattern])<10: examples[pattern].append(detail)

    recent_properties=set(); recent3_properties=set(); multi_event_properties=0
    for pid,evs in by_property.items():
        if len(evs)>=2: multi_event_properties+=1
        for a,b in zip(evs,evs[1:]):
            transitions[(a['family'],b['family'])]+=1
            code_transitions[(a['code'],b['code'])]+=1
        recent=[e for e in evs if cut365<=e['event_date']<=today]
        recent3=[e for e in evs if cut1095<=e['event_date']<=today]
        if recent: recent_properties.add(pid)
        if recent3: recent3_properties.add(pid)
        for e in recent:
            recent_family[e['family']]+=1; recent_code[e['code']]+=1

        # Factual research patterns only. These are combinations, never motivation labels.
        if len(recent)>=2:
            mark('MULTIPLE_RECORDED_EVENTS_LAST_365D',pid,{'parcel_id':pid,'event_count':len(recent),'latest_date':recent[-1]['event_date'].isoformat(),'latest_code':recent[-1]['code'],'latest_family':recent[-1]['family']})
        convey3=[e for e in recent3 if e['family']=='CONVEYANCE_DEED']
        if len(convey3)>=2:
            mark('MULTIPLE_CONVEYANCE_EVENTS_LAST_3Y',pid,{'parcel_id':pid,'conveyance_count':len(convey3),'first_date':convey3[0]['event_date'].isoformat(),'latest_date':convey3[-1]['event_date'].isoformat(),'latest_code':convey3[-1]['code']})
        # Look for a recent conveyance preceded at any earlier point by estate/fiduciary evidence.
        for e in recent:
            if e['family']=='CONVEYANCE_DEED':
                prior=[p for p in evs if p['event_date']<=e['event_date'] and p is not e and p['family']=='ESTATE_FIDUCIARY']
                if prior:
                    p=prior[-1]
                    mark('RECENT_CONVEYANCE_WITH_PRIOR_ESTATE_FIDUCIARY',pid,{'parcel_id':pid,'prior_date':p['event_date'].isoformat(),'prior_code':p['code'],'recent_date':e['event_date'].isoformat(),'recent_code':e['code']})
                    break
        # Look for a recent conveyance preceded by court/foreclosure/tax evidence.
        for e in recent:
            if e['family']=='CONVEYANCE_DEED':
                prior=[p for p in evs if p['event_date']<=e['event_date'] and p is not e and p['family']=='COURT_FORECLOSURE_TAX']
                if prior:
                    p=prior[-1]
                    mark('RECENT_CONVEYANCE_WITH_PRIOR_COURT_FORECLOSURE_TAX',pid,{'parcel_id':pid,'prior_date':p['event_date'].isoformat(),'prior_code':p['code'],'recent_date':e['event_date'].isoformat(),'recent_code':e['code']})
                    break
        if any(e['family']=='ESTATE_FIDUCIARY' for e in recent):
            latest=[e for e in recent if e['family']=='ESTATE_FIDUCIARY'][-1]
            mark('RECENT_ESTATE_FIDUCIARY_RECORD',pid,{'parcel_id':pid,'event_date':latest['event_date'].isoformat(),'document_code':latest['code'],'official_meaning':SUFFOLK_CODES.get(latest['code'])})
        if any(e['family']=='COURT_FORECLOSURE_TAX' for e in recent):
            latest=[e for e in recent if e['family']=='COURT_FORECLOSURE_TAX'][-1]
            mark('RECENT_COURT_FORECLOSURE_TAX_RECORD',pid,{'parcel_id':pid,'event_date':latest['event_date'].isoformat(),'document_code':latest['code'],'official_meaning':SUFFOLK_CODES.get(latest['code'])})

    top_trans=[{'from_family':a,'to_family':b,'transitions':n} for (a,b),n in transitions.most_common(20)]
    top_code_trans=[{'from_code':a,'from_meaning':SUFFOLK_CODES.get(a,'MISSING/UNRESOLVED'),'to_code':b,'to_meaning':SUFFOLK_CODES.get(b,'MISSING/UNRESOLVED'),'transitions':n} for (a,b),n in code_transitions.most_common(20)]
    patterns=[]
    for p,n in pattern_counts.most_common():
        patterns.append({'pattern':p,'occurrences':n,'distinct_properties':len(pattern_properties[p]),'seller_intent':False,'operational_state_change':False,'examples':examples[p]})

    return {
      'status':'ok','version':VERSION,'mode':MODE,'generated_at':datetime.now(timezone.utc).isoformat(),'market_code':MARKET,
      'population':{'market_properties':len(members),'dated_transfer_records':len(rows),'properties_with_dated_history':len(by_property),'properties_with_multiple_dated_events':multi_event_properties,'properties_with_event_last_365_days':len(recent_properties),'properties_with_event_last_3_years':len(recent3_properties)},
      'recent_event_census':{'families':[{'event_family':k,'records_last_365_days':v} for k,v in recent_family.most_common()],'codes':[{'document_code':k,'official_meaning':SUFFOLK_CODES.get(k,'MISSING/UNRESOLVED'),'records_last_365_days':v} for k,v in recent_code.most_common()]},
      'sequence_intelligence':{'top_family_transitions':top_trans,'top_document_code_transitions':top_code_trans},
      'factual_combination_research':patterns,
      'interpretation':{'policy':'Patterns describe recorded event sequences only. They are research facts, not seller intent, motivation, distress, or contact authorization.','next_if_verified':'Use validated factual combinations as additional evidence context for future change-driven investigation logic; do not promote static history alone to INVESTIGATE.'},
      'guards':{'database_writes':False,'investigate_state_touched':False,'seller_intent_inferred':False,'seller_scoring':False,'contact_authorized':False,'outreach_touched':False}
    }
