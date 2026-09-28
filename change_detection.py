#!/usr/bin/env python3
"""V16B — Suffolk-wide change detection against persistent evidence memory.

Compares the most recently observed evidence set with a durable prior state. The
first run establishes a baseline; later runs emit factual NEW / CHANGED / MISSING
observations only. This module does not score sellers or authorize contact.
"""
import hashlib, json
from datetime import datetime, timezone
from db import connect, execute

VERSION='V16B'
MODE='CHANGE_DETECTION_AGAINST_EVIDENCE_MEMORY'
PILOT='WESTHAMPTON_BEACH_NY'
EXPECTED_RESIDENTIAL=2082

def utc(): return datetime.now(timezone.utc).isoformat()

def _rows(c, sql, params=()):
    cur=execute(c,sql,params); cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def _logical_key(r):
    raw='|'.join(str(r.get(k) or '') for k in ('market_code','parcel_id','evidence_family','evidence_type','source','source_record_id'))
    return hashlib.sha256(raw.encode()).hexdigest()

def _fingerprint(payload_json, event_date, quality_state, evidence_grade):
    raw='|'.join([str(payload_json or ''),str(event_date or ''),str(quality_state or ''),str(evidence_grade or '')])
    return hashlib.sha256(raw.encode()).hexdigest()

def _ensure_schema(c):
    execute(c,"""CREATE TABLE IF NOT EXISTS evidence_current_state (
      logical_key TEXT PRIMARY KEY, market_code TEXT NOT NULL, parcel_id TEXT NOT NULL,
      evidence_family TEXT NOT NULL, evidence_type TEXT NOT NULL, source TEXT NOT NULL,
      source_record_id TEXT, evidence_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
      event_date TEXT, quality_state TEXT NOT NULL, first_baselined_at TEXT NOT NULL,
      last_compared_at TEXT NOT NULL, is_present INTEGER NOT NULL DEFAULT 1)""")
    execute(c,"""CREATE TABLE IF NOT EXISTS evidence_change_events (
      change_key TEXT PRIMARY KEY, market_code TEXT NOT NULL, parcel_id TEXT NOT NULL,
      logical_key TEXT NOT NULL, change_type TEXT NOT NULL, evidence_family TEXT NOT NULL,
      evidence_type TEXT NOT NULL, source TEXT NOT NULL, source_record_id TEXT,
      prior_evidence_key TEXT, current_evidence_key TEXT, prior_fingerprint TEXT,
      current_fingerprint TEXT, prior_event_date TEXT, current_event_date TEXT,
      prior_quality_state TEXT, current_quality_state TEXT, detected_at TEXT NOT NULL,
      seller_intent_inferred INTEGER NOT NULL DEFAULT 0, contact_authorized INTEGER NOT NULL DEFAULT 0)""")
    execute(c,'CREATE INDEX IF NOT EXISTS idx_change_events_parcel ON evidence_change_events(parcel_id)')
    execute(c,'CREATE INDEX IF NOT EXISTS idx_change_events_market ON evidence_change_events(market_code)')
    execute(c,'CREATE INDEX IF NOT EXISTS idx_change_events_family ON evidence_change_events(evidence_family)')

def _change_key(logical_key, change_type, prior_fp, current_fp):
    return hashlib.sha256('|'.join([logical_key,change_type,str(prior_fp or ''),str(current_fp or '')]).encode()).hexdigest()

def build_change_detection_v16b():
    now=utc(); c=connect()
    baseline_created=0; unchanged=0; changes_created=0; reappeared=0
    change_types={}; family_changes={}
    try:
        _ensure_schema(c)
        memberships=execute(c,'SELECT COUNT(*) FROM property_market_membership WHERE market_code=?',(PILOT,)).fetchone()[0]
        if memberships!=EXPECTED_RESIDENTIAL:
            raise RuntimeError(f'membership guard failed: expected {EXPECTED_RESIDENTIAL}, found {memberships}')
        latest_seen=execute(c,'SELECT MAX(last_seen_at) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        if not latest_seen: raise RuntimeError('no V16A evidence memory found')
        current_rows=_rows(c,"""SELECT * FROM evidence_ledger
          WHERE market_code=? AND last_seen_at=? ORDER BY parcel_id,evidence_family,source,source_record_id,evidence_key""",(PILOT,latest_seen))
        current={}
        for r in current_rows:
            lk=_logical_key(r); fp=_fingerprint(r.get('payload_json'),r.get('event_date'),r.get('quality_state'),r.get('evidence_grade'))
            # If a source emits duplicate logical IDs, deterministically keep the last evidence key.
            rr=dict(r); rr['_logical_key']=lk; rr['_fingerprint']=fp
            if lk not in current or str(rr['evidence_key'])>str(current[lk]['evidence_key']): current[lk]=rr
        prior_rows=_rows(c,'SELECT * FROM evidence_current_state WHERE market_code=?',(PILOT,))
        prior={r['logical_key']:r for r in prior_rows}
        initial_baseline=(len(prior)==0)
        if initial_baseline:
            for lk,r in current.items():
                execute(c,"""INSERT INTO evidence_current_state
                  (logical_key,market_code,parcel_id,evidence_family,evidence_type,source,source_record_id,evidence_key,fingerprint,event_date,quality_state,first_baselined_at,last_compared_at,is_present)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                  (lk,PILOT,r['parcel_id'],r['evidence_family'],r['evidence_type'],r['source'],r.get('source_record_id'),r['evidence_key'],r['_fingerprint'],r.get('event_date'),r['quality_state'],now,now))
                baseline_created+=1
        else:
            all_keys=set(prior)|set(current)
            for lk in sorted(all_keys):
                p=prior.get(lk); r=current.get(lk)
                if p is None and r is not None:
                    ctype='NEW_EVIDENCE'
                    prior_fp=None; cur_fp=r['_fingerprint']
                elif p is not None and r is None:
                    if not int(p.get('is_present') or 0):
                        execute(c,'UPDATE evidence_current_state SET last_compared_at=? WHERE logical_key=?',(now,lk)); unchanged+=1; continue
                    ctype='MISSING_FROM_LATEST_SOURCE_OBSERVATION'
                    prior_fp=p['fingerprint']; cur_fp=None
                elif p is not None and r is not None and (p['fingerprint']!=r['_fingerprint'] or not int(p.get('is_present') or 0)):
                    ctype='REAPPEARED_EVIDENCE' if not int(p.get('is_present') or 0) else 'CHANGED_EVIDENCE'
                    prior_fp=p['fingerprint']; cur_fp=r['_fingerprint']
                    if ctype=='REAPPEARED_EVIDENCE': reappeared+=1
                else:
                    execute(c,'UPDATE evidence_current_state SET last_compared_at=?,is_present=1 WHERE logical_key=?',(now,lk)); unchanged+=1; continue
                fam=(r or p)['evidence_family']; etype=(r or p)['evidence_type']; source=(r or p)['source']; sid=(r or p).get('source_record_id'); parcel=(r or p)['parcel_id']
                ck=_change_key(lk,ctype,prior_fp,cur_fp)
                exists=execute(c,'SELECT change_key FROM evidence_change_events WHERE change_key=?',(ck,)).fetchone()
                if not exists:
                    execute(c,"""INSERT INTO evidence_change_events
                      (change_key,market_code,parcel_id,logical_key,change_type,evidence_family,evidence_type,source,source_record_id,prior_evidence_key,current_evidence_key,prior_fingerprint,current_fingerprint,prior_event_date,current_event_date,prior_quality_state,current_quality_state,detected_at,seller_intent_inferred,contact_authorized)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0)""",
                      (ck,PILOT,parcel,lk,ctype,fam,etype,source,sid,p.get('evidence_key') if p else None,r.get('evidence_key') if r else None,prior_fp,cur_fp,p.get('event_date') if p else None,r.get('event_date') if r else None,p.get('quality_state') if p else None,r.get('quality_state') if r else None,now))
                    changes_created+=1; change_types[ctype]=change_types.get(ctype,0)+1; family_changes[fam]=family_changes.get(fam,0)+1
                if r is not None:
                    if p is None:
                        execute(c,"""INSERT INTO evidence_current_state
                          (logical_key,market_code,parcel_id,evidence_family,evidence_type,source,source_record_id,evidence_key,fingerprint,event_date,quality_state,first_baselined_at,last_compared_at,is_present)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                          (lk,PILOT,parcel,fam,etype,source,sid,r['evidence_key'],r['_fingerprint'],r.get('event_date'),r['quality_state'],now,now))
                    else:
                        execute(c,"""UPDATE evidence_current_state SET evidence_key=?,fingerprint=?,event_date=?,quality_state=?,last_compared_at=?,is_present=1 WHERE logical_key=?""",
                                (r['evidence_key'],r['_fingerprint'],r.get('event_date'),r['quality_state'],now,lk))
                else:
                    execute(c,'UPDATE evidence_current_state SET last_compared_at=?,is_present=0 WHERE logical_key=?',(now,lk))
        c.commit()
        state_rows=execute(c,'SELECT COUNT(*) FROM evidence_current_state WHERE market_code=?',(PILOT,)).fetchone()[0]
        present_rows=execute(c,'SELECT COUNT(*) FROM evidence_current_state WHERE market_code=? AND is_present=1',(PILOT,)).fetchone()[0]
        total_changes=execute(c,'SELECT COUNT(*) FROM evidence_change_events WHERE market_code=?',(PILOT,)).fetchone()[0]
        properties=execute(c,'SELECT COUNT(DISTINCT parcel_id) FROM evidence_current_state WHERE market_code=? AND is_present=1',(PILOT,)).fetchone()[0]
    finally: c.close()
    return {'status':'ok','version':VERSION,'mode':MODE,
      'architecture':{'scope':'SUFFOLK_COUNTY_MULTI_MARKET','pilot_market':PILOT,'principle':'BUILD_ONCE_CONFIGURE_BY_MARKET_MEASURE_LOCALLY','town_specific_change_logic':False},
      'comparison':{'evidence_observation_timestamp':latest_seen,'current_logical_evidence_records':len(current),'prior_state_records_before_run':len(prior),'initial_baseline_run':initial_baseline,'baseline_records_created':baseline_created,'unchanged_records':unchanged,'changes_created_this_run':changes_created,'change_types_created':change_types,'changes_by_evidence_family':family_changes,'reappeared_records':reappeared},
      'state':{'current_state_rows_total':state_rows,'currently_present_records':present_rows,'properties_with_current_state':properties,'change_events_total':total_changes},
      'guards':{'expected_residential':EXPECTED_RESIDENTIAL,'pilot_residential_memberships':memberships,'first_run_creates_change_events':False},
      'behavior':{'raw_source_tables_modified':False,'evidence_ledger_modified':False,'seller_intent_inferred':False,'watch_state_touched':False,'investigate_state_touched':False,'opportunity_state_touched':False,'outreach_touched':False,'contact_authorized':False},
      'next_locked_step':'V16C_FACTUAL_CHANGE_INTERPRETATION_AND_OPPORTUNITY_PATHWAYS_AFTER_V16B_VERIFICATION'}
