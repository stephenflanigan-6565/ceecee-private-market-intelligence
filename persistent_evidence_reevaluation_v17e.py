#!/usr/bin/env python3
"""V17E — Persistent Evidence Re-Evaluation.

Read-only comparison of current V17C authoritative research output against the
proven V17D persistent authoritative-research memory. No writes and no state authority.
"""
import json
from db import connect, execute
from evidence_resolution_date_semantics_v17c import build_evidence_resolution_date_semantics_v17c
from authoritative_research_evidence_memory_v17d import _stable, _key, PILOT

VERSION='V17E'
MODE='PERSISTENT_EVIDENCE_REEVALUATION'
SOURCE='Suffolk County GIS TaxParcelTransferHistory'

def _expected_observations(src):
    out=[]
    for research in src.get('resolved_research') or []:
        pid=str(research.get('parcel_id'))
        for row in research.get('authoritative_evidence') or []:
            payload=_stable({'research_request_id':research.get('research_request_id'),
                'resolution_state':research.get('resolution_state'),
                'date_semantics':research.get('date_semantics'),'county_record':row})
            out.append({'parcel_id':pid,'evidence_type':'COUNTY_TRANSFER_INSTRUMENT_METADATA',
                'source_record_id':row.get('history_sequence'),'payload':payload,
                'evidence_key':_key(pid,'COUNTY_TRANSFER_INSTRUMENT_METADATA',row.get('history_sequence'),payload)})
        payload=_stable({'research_request_id':research.get('research_request_id'),
            'evidence_target':research.get('evidence_target'),'resolution_state':research.get('resolution_state'),
            'resolved_facts':research.get('resolved_facts') or [],'remaining_unknowns':research.get('remaining_unknowns') or [],
            'date_semantics':research.get('date_semantics')})
        rid=research.get('research_request_id')
        out.append({'parcel_id':pid,'evidence_type':'RESEARCH_QUESTION_RESOLUTION','source_record_id':rid,
            'payload':payload,'evidence_key':_key(pid,'RESEARCH_QUESTION_RESOLUTION',rid,payload)})
    return out

def build_persistent_evidence_reevaluation_v17e():
    src=build_evidence_resolution_date_semantics_v17c()
    if src.get('status')!='ok':
        return {'status':'failed','version':VERSION,'error':'V17C prerequisite failed'}
    expected=_expected_observations(src)
    c=connect()
    try:
        v16a_before=execute(c,'SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        rows=execute(c,"""SELECT evidence_key,parcel_id,evidence_type,source_record_id,payload_json
            FROM authoritative_research_evidence WHERE market_code=? AND is_current=1""",(PILOT,)).fetchall()
        persisted={str(r[0]):r for r in rows}
        expected_keys={x['evidence_key'] for x in expected}
        confirmed=[x for x in expected if x['evidence_key'] in persisted]
        new=[x for x in expected if x['evidence_key'] not in persisted]
        stale=[r for k,r in persisted.items() if k not in expected_keys]
        # Same logical identity with a changed payload is a contradiction/change candidate,
        # not silently merged with prior memory.
        logical={}
        for r in rows:
            logical[(str(r[1]),str(r[2]),str(r[3] or ''))]=str(r[0])
        changed=[]
        for x in new:
            lk=(x['parcel_id'],x['evidence_type'],str(x['source_record_id'] or ''))
            if lk in logical:
                changed.append({'parcel_id':x['parcel_id'],'evidence_type':x['evidence_type'],
                    'source_record_id':x['source_record_id'],'classification':'CHANGED_OR_CONTRADICTORY_PAYLOAD'})
        changed_keys={(x['parcel_id'],x['evidence_type'],str(x['source_record_id'] or '')) for x in changed}
        genuinely_new=[x for x in new if (x['parcel_id'],x['evidence_type'],str(x['source_record_id'] or '')) not in changed_keys]
        unresolved=[]
        for research in src.get('resolved_research') or []:
            for q in research.get('remaining_unknowns') or []:
                unresolved.append({'parcel_id':str(research.get('parcel_id')),
                    'research_request_id':research.get('research_request_id'),'unknown':q})
        v16a_after=execute(c,'SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        v17d_after=execute(c,'SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?',(PILOT,)).fetchone()[0]
    finally:
        c.close()
    return {'status':'ok','version':VERSION,'mode':MODE,'market_code':PILOT,
      'source_contract':{'version':src.get('version'),'current_observations':len(expected)},
      'memory_contract':{'version':'V17D','persisted_current_rows':len(rows)},
      'reevaluation':{'confirmed_unchanged':len(confirmed),'genuinely_new':len(genuinely_new),
        'changed_or_contradictory':len(changed),'persisted_not_in_current_snapshot':len(stale),
        'remaining_unknowns':len(unresolved),'changed_or_contradictory_items':changed,
        'new_items':[{'parcel_id':x['parcel_id'],'evidence_type':x['evidence_type'],'source_record_id':x['source_record_id']} for x in genuinely_new],
        'unresolved_questions':unresolved},
      'decision':{'further_research_warranted':bool(changed or genuinely_new or unresolved),
        'reason':'UNRESOLVED_FACTUAL_QUESTIONS_REMAIN' if unresolved else ('NEW_OR_CHANGED_AUTHORITATIVE_EVIDENCE' if changed or genuinely_new else 'NO_NEW_RESEARCH_REQUIRED')},
      'protected_counts':{'v16a_evidence_ledger_before':v16a_before,'v16a_evidence_ledger_after':v16a_after,
        'v17d_authoritative_memory_after':v17d_after},
      'guards':{'database_writes':False,'v16a_evidence_ledger_modified':v16a_before!=v16a_after,
        'v17d_authoritative_memory_modified':False,'investigate_state_touched':False,'new_candidate_created':False,
        'seller_intent_inferred':False,'seller_scoring':False,'contact_authorized':False,'outreach_touched':False}}
