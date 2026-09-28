#!/usr/bin/env python3
"""V16A — Suffolk-wide persistent evidence memory foundation.

Operational infrastructure, not seller scoring. Creates a reusable market registry,
property/market membership, and append-safe evidence ledger. Westhampton Beach is
only the first configured pilot market.
"""
import hashlib, json
from datetime import datetime, timezone, date
from db import connect, execute

VERSION='V16A'
MODE='PERSISTENT_EVIDENCE_MEMORY_FOUNDATION'
PILOT='WESTHAMPTON_BEACH_NY'
EXPECTED_CANONICAL=2545
EXPECTED_RESIDENTIAL=2082
MIN_VALID_TRANSFER=date(1800,1,1)
VOLATILE={'created_at','updated_at','observed_at','ingested_at','loaded_at','last_seen_at','first_seen_at'}

def utc(): return datetime.now(timezone.utc).isoformat()
def _s(v):
    if v is None: return None
    if isinstance(v,(datetime,date)): return v.isoformat()
    return str(v)
def _date(v):
    if v in (None,''): return None
    s=str(v).strip()[:10]
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%Y%m%d'):
        try: return datetime.strptime(s,fmt).date()
        except ValueError: pass
    return None

def _rows(c, sql, params=()):
    cur=execute(c,sql,params); cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def _stable_payload(row):
    return {str(k):_s(v) for k,v in row.items() if str(k).lower() not in VOLATILE}

def _key(parcel_id,family,source,source_record_id,payload):
    raw='|'.join([str(parcel_id),family,source,str(source_record_id or ''),json.dumps(payload,sort_keys=True,separators=(',',':'))])
    return hashlib.sha256(raw.encode()).hexdigest()

def _ensure_schema(c):
    execute(c,"""CREATE TABLE IF NOT EXISTS market_registry (
      market_code TEXT PRIMARY KEY, county_name TEXT NOT NULL, town_name TEXT,
      market_name TEXT NOT NULL, district_code TEXT, status TEXT NOT NULL,
      config_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    execute(c,"""CREATE TABLE IF NOT EXISTS property_market_membership (
      market_code TEXT NOT NULL, parcel_id TEXT NOT NULL, membership_type TEXT NOT NULL,
      source_method TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
      PRIMARY KEY (market_code, parcel_id))""")
    execute(c,"""CREATE TABLE IF NOT EXISTS evidence_ledger (
      evidence_key TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, market_code TEXT,
      evidence_family TEXT NOT NULL, evidence_type TEXT NOT NULL, source TEXT NOT NULL,
      source_record_id TEXT, event_date TEXT, evidence_grade TEXT NOT NULL,
      quality_state TEXT NOT NULL, payload_json TEXT NOT NULL,
      first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1)""")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_evidence_ledger_parcel ON evidence_ledger(parcel_id)")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_evidence_ledger_market ON evidence_ledger(market_code)")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_evidence_ledger_family ON evidence_ledger(evidence_family)")

def _upsert_market(c,now):
    cfg={'architecture':'BUILD_ONCE_CONFIGURE_BY_MARKET_MEASURE_LOCALLY','county':'Suffolk','town':'Southampton','pilot':True,
         'district_code':'0905','residential_membership_method':'V15D_ORPTS_BROAD_COHORT_V1',
         'residential_cohorts':['RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND']}
    row=execute(c,'SELECT market_code FROM market_registry WHERE market_code=?',(PILOT,)).fetchone()
    if row:
        execute(c,'UPDATE market_registry SET config_json=?,updated_at=? WHERE market_code=?',(json.dumps(cfg,sort_keys=True),now,PILOT))
    else:
        execute(c,'INSERT INTO market_registry (market_code,county_name,town_name,market_name,district_code,status,config_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (PILOT,'Suffolk','Southampton','Westhampton Beach','0905','ACTIVE_PILOT',json.dumps(cfg,sort_keys=True),now,now))

def _write_evidence(c,parcel_id,family,etype,source,source_record_id,event_date,grade,quality,payload,now):
    payload=_stable_payload(payload); k=_key(parcel_id,family,source,source_record_id,payload)
    if execute(c,'SELECT evidence_key FROM evidence_ledger WHERE evidence_key=?',(k,)).fetchone():
        execute(c,'UPDATE evidence_ledger SET last_seen_at=?,is_current=1 WHERE evidence_key=?',(now,k)); return False
    execute(c,'INSERT INTO evidence_ledger (evidence_key,parcel_id,market_code,evidence_family,evidence_type,source,source_record_id,event_date,evidence_grade,quality_state,payload_json,first_seen_at,last_seen_at,is_current) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)',
            (k,str(parcel_id),PILOT,family,etype,source,_s(source_record_id),_s(event_date),grade,quality,json.dumps(payload,sort_keys=True),now,now))
    return True

def build_evidence_memory_v16a():
    now=utc(); c=connect(); inserted=0; unchanged=0; families={}; suspect_transfer_records=0
    try:
        _ensure_schema(c); _upsert_market(c,now)
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district='0905' AND status='A'").fetchone()[0]
        if canonical!=EXPECTED_CANONICAL: raise RuntimeError(f'canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}')
        members=_rows(c,"""SELECT p.parcel_id,pc.cohort,pc.method_version FROM properties p
          JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          WHERE p.district='0905' AND p.status='A' AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
          AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND') ORDER BY p.parcel_id""")
        if len(members)!=EXPECTED_RESIDENTIAL: raise RuntimeError(f'residential guard failed: expected {EXPECTED_RESIDENTIAL}, found {len(members)}')
        pids={str(x['parcel_id']) for x in members}
        for m in members:
            pid=str(m['parcel_id']); old=execute(c,'SELECT parcel_id FROM property_market_membership WHERE market_code=? AND parcel_id=?',(PILOT,pid)).fetchone()
            if old: execute(c,'UPDATE property_market_membership SET last_seen_at=? WHERE market_code=? AND parcel_id=?',(now,PILOT,pid))
            else: execute(c,'INSERT INTO property_market_membership (market_code,parcel_id,membership_type,source_method,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?)',(PILOT,pid,'RESIDENTIAL_SIDE',str(m['method_version']),now,now))
            ok=_write_evidence(c,pid,'PROPERTY_CONTEXT','RESIDENTIAL_CLASSIFICATION','V15E persisted classification',m['method_version'],None,'A','VALID',m,now)
            inserted+=int(ok); unchanged+=int(not ok); families['PROPERTY_CONTEXT']=families.get('PROPERTY_CONTEXT',0)+1
        assessments=_rows(c,"SELECT * FROM assessment_evidence WHERE roll_year=2025")
        for r in assessments:
            pid=str(r.get('parcel_id'))
            if pid not in pids: continue
            sid=r.get('source_record_id') or r.get('sbl') or r.get('parcel_id')
            ok=_write_evidence(c,pid,'ASSESSMENT_CONTEXT','ASSESSMENT_ROLL_2025',str(r.get('source') or 'NYS ORPTS'),sid,None,'A','VALID',r,now)
            inserted+=int(ok); unchanged+=int(not ok); families['ASSESSMENT_CONTEXT']=families.get('ASSESSMENT_CONTEXT',0)+1
        owners=_rows(c,"SELECT * FROM ownership_evidence WHERE source='Suffolk TaxParcelOwner'")
        for i,r in enumerate(owners):
            pid=str(r.get('parcel_id'))
            if pid not in pids: continue
            sid=r.get('source_record_id') or r.get('owner_sequence') or r.get('sequence') or i
            ok=_write_evidence(c,pid,'OWNERSHIP','OWNER_EVIDENCE','Suffolk TaxParcelOwner',sid,None,'A','SOURCE_REPORTED',r,now)
            inserted+=int(ok); unchanged+=int(not ok); families['OWNERSHIP']=families.get('OWNERSHIP',0)+1
        transfers=_rows(c,"SELECT * FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'")
        today=date.today()
        for i,r in enumerate(transfers):
            pid=str(r.get('parcel_id'))
            if pid not in pids: continue
            d=_date(r.get('sale_date')) or _date(r.get('record_date')) or _date(r.get('document_date'))
            if d is None: quality='MISSING_DATE'; ev=None
            elif d<MIN_VALID_TRANSFER or d>today: quality='SUSPECT_DATE_EXCLUDED_FROM_DERIVED'; ev=None; suspect_transfer_records+=1
            else: quality='VALID'; ev=d
            sid=r.get('source_record_id') or r.get('history_sequence') or i
            ok=_write_evidence(c,pid,'TRANSFER_TITLE','TRANSFER_HISTORY','Suffolk TaxParcelTransferHistory',sid,ev,'A',quality,r,now)
            inserted+=int(ok); unchanged+=int(not ok); families['TRANSFER_TITLE']=families.get('TRANSFER_TITLE',0)+1
        c.commit()
        total=execute(c,'SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        covered=execute(c,'SELECT COUNT(DISTINCT parcel_id) FROM evidence_ledger WHERE market_code=?',(PILOT,)).fetchone()[0]
        memberships=execute(c,'SELECT COUNT(*) FROM property_market_membership WHERE market_code=?',(PILOT,)).fetchone()[0]
    finally: c.close()
    return {'status':'ok','version':VERSION,'mode':MODE,
      'architecture':{'scope':'SUFFOLK_COUNTY_MULTI_MARKET','pilot_market':PILOT,'westhampton_hardcoded_as_core_logic':False,
        'principle':'BUILD_ONCE_CONFIGURE_BY_MARKET_MEASURE_LOCALLY','seller_scoring':False},
      'guards':{'canonical_active_parcels':canonical,'pilot_residential_memberships':memberships,'expected_residential':EXPECTED_RESIDENTIAL},
      'evidence_memory':{'properties_with_evidence':covered,'ledger_rows_total':total,'inserted_this_run':inserted,'already_known_this_run':unchanged,
        'source_observations_processed_by_family':families,'suspect_transfer_records_preserved_but_event_date_excluded':suspect_transfer_records},
      'behavior':{'raw_source_tables_modified':False,'watch_state_touched':False,'investigate_state_touched':False,'opportunity_state_touched':False,'outreach_touched':False,
        'idempotent_evidence_keys':True,'first_seen_last_seen_memory':True},
      'next_locked_step':'V16B_CHANGE_DETECTION_AGAINST_EVIDENCE_MEMORY'}
