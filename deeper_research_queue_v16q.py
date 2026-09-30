#!/usr/bin/env python3
"""V16Q — controlled deeper-research queue.

Narrows V16P's current-event research population into an explainable queue for
additional machine research. Queue admission is NOT seller scoring, seller
intent, INVESTIGATE state, contact authorization, or outreach authority.

Admission is deliberately based on RECENT factual event combinations already
validated by V16N/V16O, not property value, prestige, acreage, or price.
"""
from collections import Counter
from datetime import datetime, timezone
from multi_evidence_candidate_context_v16p import build_multi_evidence_candidate_context_v16p

VERSION='V16Q'
MODE='READ_ONLY_CONTROLLED_DEEPER_RESEARCH_QUEUE'
MARKET='WESTHAMPTON_BEACH_NY'

# These are factual combination patterns, not motivation labels.
COMBINATION_REASONS={
    'MULTIPLE_RECORDED_EVENTS_LAST_365D',
    'RECENT_CONVEYANCE_WITH_PRIOR_ESTATE_FIDUCIARY',
    'RECENT_CONVEYANCE_WITH_PRIOR_COURT_FORECLOSURE_TAX',
}


def _research_questions(item):
    reasons=set(item.get('research_reasons') or [])
    qs=[]
    # Ownership verification is required for every deeper-research record before
    # owner-addressed use, but this endpoint never emits owner names/addresses.
    qs.append('VERIFY_CURRENT_OWNERSHIP_AND_EVENT_CHRONOLOGY')
    if 'MULTIPLE_RECORDED_EVENTS_LAST_365D' in reasons:
        qs.append('RECONCILE_MULTIPLE_RECENT_RECORDED_EVENTS')
    if 'RECENT_CONVEYANCE_WITH_PRIOR_ESTATE_FIDUCIARY' in reasons:
        qs.append('CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_ESTATE_FIDUCIARY_RECORD')
    if 'RECENT_CONVEYANCE_WITH_PRIOR_COURT_FORECLOSURE_TAX' in reasons:
        qs.append('CONFIRM_CONVEYANCE_RELATIONSHIP_TO_PRIOR_COURT_FORECLOSURE_TAX_RECORD')
    if item.get('ownership_evidence_rows',0)>1:
        qs.append('RECONCILE_MULTIPLE_CURRENT_OWNERSHIP_SOURCE_ROWS')
    return qs


def build_deeper_research_queue_v16q():
    base=build_multi_evidence_candidate_context_v16p()
    if base.get('status')!='ok':
        return {'status':'failed','version':VERSION,'error':'V16P prerequisite failed',
                'guards':{'database_writes':False,'investigate_state_touched':False,
                          'contact_authorized':False,'outreach_touched':False}}

    source=list(base.get('candidate_context',{}).get('items',[]))
    queue=[]; reason_counts=Counter(); question_counts=Counter()
    excluded={'NO_COMBINATION_REASON':0,'MISSING_REQUIRED_CONTEXT':0}

    for item in source:
        reasons=list(item.get('research_reasons') or [])
        matched=[r for r in reasons if r in COMBINATION_REASONS]
        # Required independent context was verified in V16P. Preserve this as a
        # hard gate so a later source regression cannot silently admit records.
        required=(item.get('ownership_evidence_rows',0)>0 and
                  item.get('assessment_evidence_rows',0)>0 and
                  item.get('property_context_rows',0)>0)
        if not required:
            excluded['MISSING_REQUIRED_CONTEXT']+=1
            continue
        if not matched:
            excluded['NO_COMBINATION_REASON']+=1
            continue
        qs=_research_questions(item)
        for r in matched: reason_counts[r]+=1
        for q in qs: question_counts[q]+=1
        queue.append({
            'parcel_id':item.get('parcel_id'),
            'latest_event_date':item.get('latest_event_date'),
            'latest_document_code':item.get('latest_document_code'),
            'latest_official_meaning':item.get('latest_official_meaning'),
            'latest_event_family':item.get('latest_event_family'),
            'recent_event_count_365d':item.get('recent_event_count_365d'),
            'conveyance_count_3y':item.get('conveyance_count_3y'),
            'current_evidence_records':item.get('current_evidence_records'),
            'ownership_evidence_rows':item.get('ownership_evidence_rows'),
            'assessment_evidence_rows':item.get('assessment_evidence_rows'),
            'property_context_rows':item.get('property_context_rows'),
            'transfer_title_evidence_rows':item.get('transfer_title_evidence_rows'),
            'queue_reasons':matched,
            'research_questions':qs,
            'queue_state':'DEEPER_RESEARCH',
            'seller_intent':False,
            'investigate_state_change':False,
            'contact_authorized':False,
        })

    # Operational ordering only: more independently explainable combination
    # reasons first, then newest event. This is NOT a seller score/probability.
    queue.sort(key=lambda x:(len(x['queue_reasons']),x.get('latest_event_date') or ''),reverse=True)
    return {
        'status':'ok','version':VERSION,'mode':MODE,
        'generated_at':datetime.now(timezone.utc).isoformat(),'market_code':MARKET,
        'source_population':{
            'market_properties':base.get('source_population',{}).get('market_properties'),
            'v16o_candidate_count':base.get('source_population',{}).get('v16o_candidate_count'),
            'v16p_items_profiled':len(source),
        },
        'deeper_research_queue':{
            'candidate_count':len(queue),'items':queue,
            'admission_reason_counts':dict(sorted(reason_counts.items())),
            'research_question_counts':dict(sorted(question_counts.items())),
            'excluded_counts':excluded,
        },
        'interpretation':{
            'purpose':'Create the first controlled machine deeper-research queue from recent factual event combinations plus complete independent context.',
            'admission_rule':'Requires current ownership, assessment and property context plus at least one validated recent combination reason. Property price, value, size, prestige and luxury status are not admission criteria.',
            'policy':'DEEPER_RESEARCH means spend more machine research effort. It is not seller intent, motivation, distress, a seller lead, INVESTIGATE state, or contact authorization.',
            'next_if_verified':'Resolve the listed factual research questions for this queue, beginning with current ownership and event chronology, before considering any operational INVESTIGATE promotion.'
        },
        'guards':{
            'database_writes':False,'investigate_state_touched':False,
            'seller_intent_inferred':False,'seller_scoring':False,
            'contact_authorized':False,'outreach_touched':False,
            'owner_names_addresses_emitted':False,'price_or_luxury_gate_used':False,
        }
    }
