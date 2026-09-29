#!/usr/bin/env python3
"""V16L — read-only title/transfer event intelligence over already-persisted Suffolk evidence.
No seller intent, scoring, state promotion, contact authorization, or database writes.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from db import connect, execute

VERSION = "V16L"
MODE = "READ_ONLY_TITLE_TRANSFER_EVENT_INTELLIGENCE"
MARKET = "WESTHAMPTON_BEACH_NY"
SOURCE = "Suffolk TaxParcelTransferHistory"


def _rows(cur):
    cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]


def _date(v):
    if v in (None, ""): return None
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    s=str(v)[:10]
    try: return date.fromisoformat(s)
    except Exception: return None


def build_title_transfer_event_intelligence_v16l():
    c=connect()
    try:
        members={str(r[0]) for r in execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=?",(MARKET,)).fetchall()}
        raw=_rows(execute(c,"SELECT parcel_id, record_date, document_date, entry_date, document_number, document_code, history_sequence, source FROM transfers WHERE source=?",(SOURCE,)))
    finally:
        c.close()

    rows=[r for r in raw if str(r.get('parcel_id')) in members]
    today=date.today(); cut365=today-timedelta(days=365); cut1095=today-timedelta(days=1095)
    code_counts=Counter(); code_parcels={}; recent365=Counter(); recent1095=Counter(); missing_code=0; valid_dated=0
    latest_by_parcel={}
    for r in rows:
        code=str(r.get('document_code') or '').strip().upper()
        if not code:
            code='[MISSING]'; missing_code+=1
        code_counts[code]+=1
        code_parcels.setdefault(code,set()).add(str(r.get('parcel_id')))
        d=_date(r.get('record_date')) or _date(r.get('document_date')) or _date(r.get('entry_date'))
        if d and d <= today:
            valid_dated+=1
            if d >= cut365: recent365[code]+=1
            if d >= cut1095: recent1095[code]+=1
            pid=str(r.get('parcel_id'))
            if pid not in latest_by_parcel or d > latest_by_parcel[pid]: latest_by_parcel[pid]=d

    codes=[]
    for code,n in code_counts.most_common():
        codes.append({
            'document_code':code,
            'records':n,
            'distinct_properties':len(code_parcels.get(code,set())),
            'records_last_365_days':recent365.get(code,0),
            'records_last_3_years':recent1095.get(code,0),
            'meaning':'UNMAPPED_SOURCE_CODE' if code!='[MISSING]' else 'MISSING_SOURCE_CODE',
            'seller_intent':False,
        })

    return {
        'status':'ok','version':VERSION,'mode':MODE,'generated_at':datetime.now(timezone.utc).isoformat(),
        'market_code':MARKET,
        'population':{'market_properties':len(members),'transfer_records':len(rows),'properties_with_dated_transfer_activity':len(latest_by_parcel)},
        'document_code_census':{'distinct_codes':len(code_counts),'missing_code_records':missing_code,'codes':codes},
        'date_profile':{'valid_dated_records':valid_dated,'records_last_365_days':sum(recent365.values()),'records_last_3_years':sum(recent1095.values())},
        'interpretation':{
            'purpose':'Expose the factual Suffolk document-code/event vocabulary already present in production so event meanings can be mapped from authoritative evidence before any operational weighting.',
            'classification_policy':'No document-code meaning is invented in V16L. Unknown source codes remain explicitly unmapped.',
            'next_if_verified':'Map source document codes to authoritative factual event families, then test event combinations without promoting seller intent.'
        },
        'guards':{'database_writes':False,'investigate_state_touched':False,'seller_intent_inferred':False,'seller_scoring':False,'contact_authorized':False,'outreach_touched':False}
    }
