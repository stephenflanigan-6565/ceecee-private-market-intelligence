#!/usr/bin/env python3
"""V17D — Persistent Authoritative Research Evidence Memory.

Additive provenance-preserving memory rail derived from the proven V16A persistence
pattern. Does not rewrite V16A evidence_ledger or any investigation/contact state.
"""
import hashlib, json
from datetime import datetime, timezone, date
from db import connect, execute
from evidence_resolution_date_semantics_v17c import build_evidence_resolution_date_semantics_v17c

VERSION='V17D'
MODE='PERSISTENT_AUTHORITATIVE_RESEARCH_EVIDENCE_MEMORY'
PILOT='WESTHAMPTON_BEACH_NY'
SOURCE='Suffolk County GIS TaxParcelTransferHistory'
VOLATILE={'generated_at','retrieved_at','observed_at','ingested_at','loaded_at','last_seen_at','first_seen_at'}

def utc(): return datetime.now(timezone.utc).isoformat()
def _s(v):
    if v is None: return None
    if isinstance(v,(datetime,date)): return v.isoformat()
    return str(v)
def _stable(v):
    if isinstance(v,dict): return {str(k):_stable(x) for k,x in v.items() if str(k).lower() not in VOLATILE}
    if isinstance(v,list): return [_stable(x) for x in v]
    return _s(v) if isinstance(v,(datetime,date)) else v

def _key(parcel_id,evidence_type,source_record_id,payload):
    raw='|'.join([str(parcel_id),evidence_type,SOURCE,str(source_record_id or ''),json.dumps(payload,sort_keys=True,separators=(',',':'))])
    return hashlib.sha256(raw.encode()).hexdigest()

def _ensure_schema(c):
    execute(c,"""CREATE TABLE IF NOT EXISTS authoritative_research_evidence (
      evidence_key TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, market_code TEXT NOT NULL,
      evidence_family TEXT NOT NULL, evidence_type TEXT NOT NULL, source TEXT NOT NULL,
      source_record_id TEXT, event_date TEXT, evidence_grade TEXT NOT NULL,
      quality_state TEXT NOT NULL, payload_json TEXT NOT NULL,
      first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1)""")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_auth_research_parcel ON authoritative_research_evidence(parcel_id)")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_auth_research_market ON authoritative_research_evidence(market_code)")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_auth_research_type ON authoritative_research_evidence(evidence_type)")

def _write(c,parcel_id,evidence_type,source_record_id,event_date,quality,payload,now):
    payload=_stable(payload)
    k=_key(parcel_id,evidence_type,source_record_id,payload)
    if execute(c,'SELECT evidence_key FROM authoritative_research_evidence WHERE evidence_key=?',(k,)).fetchone():
        execute(c,'UPDATE authoritative_research_evidence SET last_seen_at=?,is_current=1 WHERE evidence_key=?',(now,k))
        return False
    execute(c,"""INSERT INTO authoritative_research_evidence
      (evidence_key,parcel_id,market_code,evidence_family,evidence_type,source,source_record_id,event_date,evidence_grade,quality_state,payload_json,first_seen_at,last_seen_at,is_current)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
      (k,str(parcel_id),PILOT,'AUTHORITATIVE_RESEARCH',evidence_type,SOURCE,_s(source_record_id),_s(event_date),'A',quality,json.dumps(payload,sort_keys=True),now,now))
    return True

def build_authoritative_research_evidence_memory_v17d():
    src=build_evidence_resolution_date_semantics_v17c()
    if src.get('status')!='ok':
        return {'status':'failed','version':VERSION,'error':'V17C prerequisite failed'}
    now=utc(); c=connect(); inserted=unchanged=0; by_type={}
    try:
        _ensure_schema(c)
        # Guard: original V16A ledger must exist and remain the protected raw/source evidence rail.
        original_before=execute(c,'SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        if original_before < 18001:
            raise RuntimeError(f'protected V16A evidence ledger guard failed: expected at least 18001, found {original_before}')

        for research in src.get('resolved_research') or []:
            pid=str(research.get('parcel_id'))
            for row in research.get('authoritative_evidence') or []:
                seq=row.get('history_sequence')
                etype='COUNTY_TRANSFER_INSTRUMENT_METADATA'
                quality='AUTHORITATIVE_IDENTITY_COMPLETE' if row.get('record_date') and row.get('liber_page') else 'AUTHORITATIVE_ROW_IDENTITY_INCOMPLETE'
                payload={'research_request_id':research.get('research_request_id'),
                         'resolution_state':research.get('resolution_state'),
                         'date_semantics':research.get('date_semantics'),
                         'county_record':row}
                ok=_write(c,pid,etype,seq,row.get('record_date'),quality,payload,now)
                inserted+=int(ok); unchanged+=int(not ok); by_type[etype]=by_type.get(etype,0)+1

            # Persist the resolution itself separately from source-record metadata.
            resolution_payload={'research_request_id':research.get('research_request_id'),
                                'evidence_target':research.get('evidence_target'),
                                'resolution_state':research.get('resolution_state'),
                                'resolved_facts':research.get('resolved_facts') or [],
                                'remaining_unknowns':research.get('remaining_unknowns') or [],
                                'date_semantics':research.get('date_semantics')}
            rid=research.get('research_request_id')
            ok=_write(c,pid,'RESEARCH_QUESTION_RESOLUTION',rid,None,'FACTUAL_RESOLUTION_WITH_EXPLICIT_UNKNOWNS',resolution_payload,now)
            inserted+=int(ok); unchanged+=int(not ok); by_type['RESEARCH_QUESTION_RESOLUTION']=by_type.get('RESEARCH_QUESTION_RESOLUTION',0)+1

        c.commit()
        original_after=execute(c,'SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        total=execute(c,'SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?',(PILOT,)).fetchone()[0]
        parcels=execute(c,'SELECT COUNT(DISTINCT parcel_id) FROM authoritative_research_evidence WHERE market_code=?',(PILOT,)).fetchone()[0]
        if original_after != original_before:
            raise RuntimeError('protected V16A evidence ledger row count changed during V17D')
    finally:
        c.close()
    return {'status':'ok','version':VERSION,'mode':MODE,'market_code':PILOT,
      'source_contract':{'version':src.get('version'),'research_questions_received':len(src.get('resolved_research') or [])},
      'persistence':{'table':'authoritative_research_evidence','rows_total':total,'properties_with_enrichment':parcels,
        'inserted_this_run':inserted,'already_known_this_run':unchanged,'observations_processed_by_type':by_type,
        'idempotent_evidence_keys':True,'first_seen_last_seen_memory':True},
      'protected_v16a_ledger':{'rows_before':original_before,'rows_after':original_after,'unchanged':original_before==original_after},
      'guards':{'raw_source_tables_modified':False,'v16a_evidence_ledger_modified':False,'investigate_state_touched':False,
        'new_candidate_created':False,'source_history_silently_corrected':False,'recorddate_fabricated_from_entrydate':False,
        'manual_ownership_verification_bypassed':False,'seller_intent_inferred':False,'seller_scoring':False,
        'contact_authorized':False,'outreach_touched':False},
      'next_locked_test':'RUN_V17D_AGAIN_EXPECT_ZERO_INSERTS'}
