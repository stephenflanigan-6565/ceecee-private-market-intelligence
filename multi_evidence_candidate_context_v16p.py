#!/usr/bin/env python3
"""V16P — multi-evidence candidate context.
Read-only cross-check of V16O current-event candidates against independent PMI evidence families already held.
No seller intent, scoring, INVESTIGATE mutation, contact authorization, or DB writes.
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from db import connect, execute
from current_event_attention_v16o import build_current_event_attention_v16o

VERSION='V16P'
MODE='READ_ONLY_MULTI_EVIDENCE_CANDIDATE_CONTEXT'
MARKET='WESTHAMPTON_BEACH_NY'


def _rows(cur):
    cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]


def _safe_json(v):
    if isinstance(v,dict): return v
    try: return json.loads(v or '{}')
    except Exception: return {}


def build_multi_evidence_candidate_context_v16p():
    base=build_current_event_attention_v16o()
    if base.get('status')!='ok':
        return {'status':'failed','version':VERSION,'error':'V16O prerequisite failed','guards':{'database_writes':False}}
    # V16O returns top 50 but candidate_count may be larger. Reconstruct candidate parcel set from
    # the same read-only function output currently exposed; this module intentionally profiles the
    # review population returned to the operator, not hidden candidates.
    candidates=list(base.get('attention_research',{}).get('items',[]))
    pids=[str(x['parcel_id']) for x in candidates]
    evidence=defaultdict(list)
    if pids:
        c=connect()
        try:
            marks=','.join('?' for _ in pids)
            q=f"SELECT parcel_id,evidence_family,evidence_type,source,event_date,evidence_grade,quality_state,payload_json,is_current FROM evidence_ledger WHERE market_code=? AND parcel_id IN ({marks}) AND is_current=1"
            for r in _rows(execute(c,q,tuple([MARKET]+pids))):
                evidence[str(r['parcel_id'])].append(r)
        finally:
            c.close()

    out=[]; stack_counts=Counter(); missing_counts=Counter(); owner_row_hist=Counter()
    for cand in candidates:
        pid=str(cand['parcel_id']); evs=evidence.get(pid,[])
        fam=Counter(str(e.get('evidence_family')) for e in evs)
        owner_rows=[e for e in evs if e.get('evidence_family')=='OWNERSHIP']
        assess=[e for e in evs if e.get('evidence_family')=='ASSESSMENT_CONTEXT']
        prop=[e for e in evs if e.get('evidence_family')=='PROPERTY_CONTEXT']
        transfer=[e for e in evs if e.get('evidence_family')=='TRANSFER_TITLE']
        owner_row_hist[len(owner_rows)]+=1
        independent_context=[]
        if owner_rows: independent_context.append('CURRENT_OWNERSHIP_EVIDENCE_PRESENT')
        else: missing_counts['OWNERSHIP']+=1
        if assess: independent_context.append('ASSESSMENT_CONTEXT_PRESENT')
        else: missing_counts['ASSESSMENT_CONTEXT']+=1
        if prop: independent_context.append('PROPERTY_CONTEXT_PRESENT')
        else: missing_counts['PROPERTY_CONTEXT']+=1
        # Multiple source-reported owner rows are factual complexity only; they do not mean motivation.
        if len(owner_rows)>1: independent_context.append('MULTIPLE_CURRENT_OWNER_EVIDENCE_ROWS')
        # Keep only non-sensitive, operational metadata from owner payloads: source-row count and whether
        # source payloads exist. Names/addresses are deliberately not emitted by this research endpoint.
        owner_payloads=sum(1 for e in owner_rows if _safe_json(e.get('payload_json')))
        item=dict(cand)
        item.update({
            'evidence_family_counts':dict(sorted(fam.items())),
            'current_evidence_records':len(evs),
            'ownership_evidence_rows':len(owner_rows),
            'ownership_payload_rows':owner_payloads,
            'assessment_evidence_rows':len(assess),
            'property_context_rows':len(prop),
            'transfer_title_evidence_rows':len(transfer),
            'independent_context':independent_context,
            'independent_context_count':len(independent_context),
            'seller_intent':False,'investigate_state_change':False,'contact_authorized':False,
        })
        stack_counts[len(independent_context)]+=1
        out.append(item)
    out=sorted(out,key=lambda x:(x['research_reason_count'],x['independent_context_count'],x['latest_event_date']),reverse=True)
    return {
      'status':'ok','version':VERSION,'mode':MODE,'generated_at':datetime.now(timezone.utc).isoformat(),'market_code':MARKET,
      'source_population':{'v16o_candidate_count':base.get('attention_research',{}).get('candidate_count',0),'v16o_items_profiled':len(candidates),'market_properties':base.get('population',{}).get('market_properties')},
      'cross_evidence_summary':{'context_stack_histogram':{str(k):v for k,v in sorted(stack_counts.items())},'ownership_row_histogram':{str(k):v for k,v in sorted(owner_row_hist.items())},'missing_required_context_counts':dict(sorted(missing_counts.items()))},
      'candidate_context':{'items':out,'items_returned':len(out)},
      'interpretation':{
        'purpose':'Cross-check current recorded-event research candidates against independent property, ownership, and assessment evidence already held by PMI.',
        'policy':'Presence, multiplicity, or combination of evidence is factual context only. It is not seller intent, motivation, distress, lead status, INVESTIGATE state, or contact authorization.',
        'next_if_verified':'Use this cross-evidence profile to identify which current-event candidates have enough factual context for a controlled deeper-research queue and which evidence rails remain missing.'},
      'guards':{'database_writes':False,'investigate_state_touched':False,'seller_intent_inferred':False,'seller_scoring':False,'contact_authorized':False,'outreach_touched':False,'owner_names_addresses_emitted':False}
    }
