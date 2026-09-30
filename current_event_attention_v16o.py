#!/usr/bin/env python3
"""V16O — current factual event attention research.
Read-only bridge from V16M/V16N into a small, explainable review population.
It does NOT infer seller intent, score sellers, mutate INVESTIGATE, authorize contact, or write DB state.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from db import connect, execute
from title_transfer_authority_v16m import SUFFOLK_CODES, FAMILY

VERSION='V16O'
MODE='READ_ONLY_CURRENT_EVENT_ATTENTION_RESEARCH'
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
    return str(r.get('document_code') or '').strip().upper() or '[MISSING]'

def _family(code):
    return FAMILY.get(code,'UNRESOLVED_SOURCE') if code in SUFFOLK_CODES else 'UNRESOLVED_SOURCE'

def build_current_event_attention_v16o():
    c=connect()
    try:
        members={str(r[0]) for r in execute(c,'SELECT parcel_id FROM property_market_membership WHERE market_code=?',(MARKET,)).fetchall()}
        raw=_rows(execute(c,'SELECT parcel_id, record_date, document_date, entry_date, document_number, document_code, history_sequence FROM transfers WHERE source=?',(SOURCE,)))
    finally:
        c.close()

    by_property=defaultdict(list)
    for r in raw:
        pid=str(r.get('parcel_id'))
        if pid not in members: continue
        d=_event_date(r)
        if not d: continue
        code=_code(r)
        by_property[pid].append({'event_date':d,'code':code,'family':_family(code),'document_number':r.get('document_number'),'history_sequence':r.get('history_sequence')})
    for evs in by_property.values():
        evs.sort(key=lambda x:(x['event_date'],str(x.get('history_sequence') or ''),str(x.get('document_number') or '')))

    today=date.today(); cut365=today-timedelta(days=365); cut1095=today-timedelta(days=1095)
    items=[]; reason_counts=defaultdict(int)
    for pid,evs in by_property.items():
        recent=[e for e in evs if cut365<=e['event_date']<=today]
        if not recent: continue
        recent3=[e for e in evs if cut1095<=e['event_date']<=today]
        reasons=[]
        estate_recent=[e for e in recent if e['family']=='ESTATE_FIDUCIARY']
        court_recent=[e for e in recent if e['family']=='COURT_FORECLOSURE_TAX']
        convey3=[e for e in recent3 if e['family']=='CONVEYANCE_DEED']
        if estate_recent: reasons.append('RECENT_ESTATE_FIDUCIARY_RECORD')
        if court_recent: reasons.append('RECENT_COURT_FORECLOSURE_TAX_RECORD')
        if len(recent)>=2: reasons.append('MULTIPLE_RECORDED_EVENTS_LAST_365D')
        if len(convey3)>=2: reasons.append('MULTIPLE_CONVEYANCE_EVENTS_LAST_3Y')
        # Recent conveyance after earlier estate/court evidence is factual context only.
        for e in recent:
            if e['family']!='CONVEYANCE_DEED': continue
            if any(p['event_date']<=e['event_date'] and p is not e and p['family']=='ESTATE_FIDUCIARY' for p in evs):
                reasons.append('RECENT_CONVEYANCE_WITH_PRIOR_ESTATE_FIDUCIARY'); break
        for e in recent:
            if e['family']!='CONVEYANCE_DEED': continue
            if any(p['event_date']<=e['event_date'] and p is not e and p['family']=='COURT_FORECLOSURE_TAX' for p in evs):
                reasons.append('RECENT_CONVEYANCE_WITH_PRIOR_COURT_FORECLOSURE_TAX'); break
        reasons=list(dict.fromkeys(reasons))
        if not reasons: continue
        for x in reasons: reason_counts[x]+=1
        latest=recent[-1]
        items.append({'parcel_id':pid,'latest_event_date':latest['event_date'].isoformat(),'latest_document_code':latest['code'],
                      'latest_official_meaning':SUFFOLK_CODES.get(latest['code'],'MISSING/UNRESOLVED'),
                      'latest_event_family':latest['family'],'recent_event_count_365d':len(recent),
                      'conveyance_count_3y':len(convey3),'research_reasons':reasons,'research_reason_count':len(reasons),
                      'seller_intent':False,'investigate_state_change':False,'contact_authorized':False})
    # Deterministic research ordering: more independent factual reasons, then newest event, then parcel id.
    items.sort(key=lambda x:(-x['research_reason_count'],x['latest_event_date'],x['parcel_id']), reverse=False)
    # Correct date direction while preserving reason-count priority.
    items=sorted(items,key=lambda x:x['latest_event_date'],reverse=True)
    items=sorted(items,key=lambda x:x['research_reason_count'],reverse=True)
    return {
      'status':'ok','version':VERSION,'mode':MODE,'generated_at':datetime.now(timezone.utc).isoformat(),'market_code':MARKET,
      'population':{'market_properties':len(members),'properties_with_dated_history':len(by_property),'properties_with_event_last_365_days':sum(1 for evs in by_property.values() if any(cut365<=e['event_date']<=today for e in evs))},
      'attention_research':{'candidate_count':len(items),'reason_counts':dict(sorted(reason_counts.items())),'items':items[:50],'items_returned':min(50,len(items))},
      'interpretation':{'purpose':'Produce a small explainable factual research population from recent recorded events and validated V16N combinations.','policy':'Research attention is not seller intent, motivation, distress, lead status, INVESTIGATE state, or contact authorization. Static old history alone cannot enter this output; every item requires at least one recorded event within the last 365 days.','next_if_verified':'Cross-check these current-event candidates against additional independent evidence already held by PMI before any operational INVESTIGATE promotion.'},
      'guards':{'database_writes':False,'investigate_state_touched':False,'seller_intent_inferred':False,'seller_scoring':False,'contact_authorized':False,'outreach_touched':False}
    }
