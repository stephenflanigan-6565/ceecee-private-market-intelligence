#!/usr/bin/env python3
"""V16R — factual deeper-research resolution.

Answers V16Q's machine research questions from evidence already held by PMI.
Read-only. It does not infer seller intent, motivation, distress, lead status,
INVESTIGATE state, contact authorization, or outreach authority.
"""
import hashlib, json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from db import connect, execute
from deeper_research_queue_v16q import build_deeper_research_queue_v16q
from title_transfer_authority_v16m import SUFFOLK_CODES, FAMILY

VERSION='V16R'
MODE='READ_ONLY_FACTUAL_DEEPER_RESEARCH_RESOLUTION'
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


def _payload(v):
    if isinstance(v,dict): return v
    try: return json.loads(v or '{}')
    except Exception: return {}


def _fingerprint(payload):
    # Compare source payload equality without emitting names, addresses, or payload contents.
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]


def _prior(events, recent_event, family):
    eligible=[e for e in events if e['event_date'] < recent_event['event_date'] and e['family']==family]
    return eligible[-1] if eligible else None


def build_factual_research_resolution_v16r():
    base=build_deeper_research_queue_v16q()
    if base.get('status')!='ok':
        return {'status':'failed','version':VERSION,'error':'V16Q prerequisite failed',
                'guards':{'database_writes':False,'investigate_state_touched':False,
                          'contact_authorized':False,'outreach_touched':False}}

    queue=list(base.get('deeper_research_queue',{}).get('items',[]))
    pids=[str(x.get('parcel_id')) for x in queue if x.get('parcel_id')]
    transfers=defaultdict(list); owners=defaultdict(list)
    if pids:
        c=connect()
        try:
            marks=','.join('?' for _ in pids)
            tq=("SELECT parcel_id,record_date,document_date,entry_date,document_number,document_code,history_sequence "
                f"FROM transfers WHERE source=? AND parcel_id IN ({marks})")
            for r in _rows(execute(c,tq,tuple([SOURCE]+pids))):
                d=_event_date(r)
                if not d: continue
                code=_code(r)
                transfers[str(r['parcel_id'])].append({
                    'event_date':d,'document_code':code,'official_meaning':SUFFOLK_CODES.get(code,'MISSING/UNRESOLVED'),
                    'event_family':_family(code),'document_number':r.get('document_number'),
                    'history_sequence':r.get('history_sequence')})
            oq=("SELECT parcel_id,source,evidence_grade,quality_state,payload_json,is_current "
                f"FROM evidence_ledger WHERE market_code=? AND evidence_family='OWNERSHIP' AND is_current=1 AND parcel_id IN ({marks})")
            for r in _rows(execute(c,oq,tuple([MARKET]+pids))): owners[str(r['parcel_id'])].append(r)
        finally:
            c.close()

    for evs in transfers.values():
        evs.sort(key=lambda x:(x['event_date'],str(x.get('history_sequence') or ''),str(x.get('document_number') or '')))

    results=[]; resolution_counts=Counter(); owner_counts=Counter()
    for q in queue:
        pid=str(q['parcel_id']); evs=transfers.get(pid,[]); ows=owners.get(pid,[])
        payload_fps=[_fingerprint(_payload(o.get('payload_json'))) for o in ows if _payload(o.get('payload_json'))]
        distinct_payloads=len(set(payload_fps))
        if not ows: owner_recon='NO_CURRENT_OWNERSHIP_EVIDENCE'
        elif len(ows)==1: owner_recon='SINGLE_CURRENT_OWNERSHIP_SOURCE_ROW'
        elif distinct_payloads<=1: owner_recon='MULTIPLE_EQUIVALENT_CURRENT_OWNERSHIP_ROWS'
        else: owner_recon='MULTIPLE_DISTINCT_CURRENT_OWNERSHIP_ROWS_REQUIRE_VERIFICATION'
        owner_counts[owner_recon]+=1

        answers=[]
        requested=set(q.get('research_questions') or [])
        latest=evs[-1] if evs else None
        if 'VERIFY_CURRENT_OWNERSHIP_AND_EVENT_CHRONOLOGY' in requested:
            state='FACTUAL_CONTEXT_PRESENT' if ows and evs else 'INCOMPLETE_CONTEXT'
            answers.append({'question':'VERIFY_CURRENT_OWNERSHIP_AND_EVENT_CHRONOLOGY','resolution':state,
                            'current_ownership_source_rows':len(ows),'ownership_reconciliation':owner_recon,
                            'ownership_verification_gate':'PROBABLE_PENDING_MANUAL_VERIFICATION',
                            'dated_title_events':len(evs),'latest_event_date':latest['event_date'].isoformat() if latest else None,
                            'latest_document_code':latest['document_code'] if latest else None,
                            'latest_official_meaning':latest['official_meaning'] if latest else None})
            resolution_counts[state]+=1

        if 'RECONCILE_MULTIPLE_RECENT_RECORDED_EVENTS' in requested:
            cutoff=date.today().replace(year=date.today().year-1) if not (date.today().month==2 and date.today().day==29) else date(date.today().year-1,2,28)
            recent=[e for e in evs if cutoff<=e['event_date']<=date.today()]
            same_day=len({e['event_date'] for e in recent}) < len(recent)
            state='MULTIPLE_RECENT_EVENTS_CHRONOLOGY_RESOLVED' if len(recent)>=2 else 'RECENT_EVENT_COUNT_NOT_REPRODUCED'
            answers.append({'question':'RECONCILE_MULTIPLE_RECENT_RECORDED_EVENTS','resolution':state,
                            'recent_event_count':len(recent),'distinct_event_dates':len({e['event_date'] for e in recent}),
                            'same_day_ordering_present':same_day,
                            'events':[{'event_date':e['event_date'].isoformat(),'document_code':e['document_code'],
                                       'official_meaning':e['official_meaning'],'event_family':e['event_family']} for e in recent[-6:]]})
            resolution_counts[state]+=1

        for fam,question in [('ESTATE_FIDUCIARY','CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_ESTATE_FIDUCIARY_RECORD'),
                             ('COURT_FORECLOSURE_TAX','CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_COURT_FORECLOSURE_TAX_RECORD')]:
            if question not in requested: continue
            recent_conveys=[e for e in evs if e['event_family']=='CONVEYANCE_DEED' and (date.today()-e['event_date']).days<=365]
            pair=None
            for conv in reversed(recent_conveys):
                p=_prior(evs,conv,fam)
                if p: pair=(p,conv); break
            state='ORDERED_PRIOR_EVENT_AND_RECENT_CONVEYANCE_CONFIRMED' if pair else 'ORDERED_RELATIONSHIP_NOT_REPRODUCED'
            ans={'question':question,'resolution':state}
            if pair:
                p,conv=pair
                ans.update({'prior_event_date':p['event_date'].isoformat(),'prior_document_code':p['document_code'],
                            'prior_official_meaning':p['official_meaning'],'conveyance_date':conv['event_date'].isoformat(),
                            'conveyance_document_code':conv['document_code'],'conveyance_official_meaning':conv['official_meaning'],
                            'days_between_recorded_events':(conv['event_date']-p['event_date']).days,
                            'relationship_scope':'RECORDED_CHRONOLOGY_ONLY'})
            answers.append(ans); resolution_counts[state]+=1

        if 'RECONCILE_MULTIPLE_CURRENT_OWNERSHIP_SOURCE_ROWS' in requested:
            state=owner_recon
            answers.append({'question':'RECONCILE_MULTIPLE_CURRENT_OWNERSHIP_SOURCE_ROWS','resolution':state,
                            'current_source_rows':len(ows),'distinct_payload_fingerprints':distinct_payloads,
                            'manual_owner_verification_required':True})
            resolution_counts[state]+=1

        results.append({
            'parcel_id':pid,'queue_state':'DEEPER_RESEARCH','queue_reasons':q.get('queue_reasons',[]),
            'questions_requested':len(requested),'questions_answered':len(answers),'research_answers':answers,
            'chronology_tail':[{'event_date':e['event_date'].isoformat(),'document_code':e['document_code'],
                                'official_meaning':e['official_meaning'],'event_family':e['event_family']} for e in evs[-8:]],
            'ownership_reconciliation':owner_recon,
            'ownership_verification_gate':'PROBABLE_PENDING_MANUAL_VERIFICATION',
            'seller_intent':False,'investigate_state_change':False,'contact_authorized':False,
        })

    return {
      'status':'ok','version':VERSION,'mode':MODE,'generated_at':datetime.now(timezone.utc).isoformat(),'market_code':MARKET,
      'source_population':{'market_properties':base.get('source_population',{}).get('market_properties'),
                           'v16q_deeper_research_candidates':len(queue),'items_resolved':len(results)},
      'resolution_summary':{'research_answer_resolution_counts':dict(sorted(resolution_counts.items())),
                            'ownership_reconciliation_counts':dict(sorted(owner_counts.items()))},
      'resolved_research':{'items':results,'items_returned':len(results)},
      'interpretation':{
        'purpose':'Answer V16Q factual research questions using title chronology and current ownership evidence already held by PMI.',
        'policy':'A resolved chronology or ownership-source reconciliation is factual research only. It does not establish seller intent, motivation, distress, lead status, INVESTIGATE state, or contact authorization.',
        'ownership_policy':'The temporary Ownership Verification Gate remains in force. Source evidence may be reconciled here, but owner-addressed outreach remains blocked until manual authoritative verification.',
        'next_if_verified':'Use resolved factual answers to separate records needing additional source verification from records whose chronology is sufficiently understood for a later, separately governed investigation-promotion test.'},
      'guards':{'database_writes':False,'investigate_state_touched':False,'seller_intent_inferred':False,
                'seller_scoring':False,'contact_authorized':False,'outreach_touched':False,
                'owner_names_addresses_emitted':False,'sensitive_motivation_inferred':False}
    }
