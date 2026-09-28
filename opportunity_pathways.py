#!/usr/bin/env python3
"""V16C — Factual evidence interpretation and seller-opportunity research pathways.

Turns normalized evidence/change memory into explainable *research reasons* without
claiming seller intent, ranking owners, authorizing contact, or setting WATCH /
INVESTIGATE state. Core logic is market-agnostic; market membership/configuration
selects the population.
"""
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from db import connect, execute

VERSION='V16C'
MODE='FACTUAL_EVIDENCE_INTERPRETATION_AND_OPPORTUNITY_PATHWAYS'
PILOT='WESTHAMPTON_BEACH_NY'
EXPECTED_RESIDENTIAL=2082

# Research interpretation only. These are not seller scores or contact rules.
RECENT_TITLE_DAYS=1095       # factual recent-title-activity lens
LONG_GAP_DAYS=365*20         # research gap lens, not owner tenure
MIN_VALID_HISTORY=3


def _rows(c, sql, params=()):
    cur=execute(c,sql,params); cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def _parse_date(v):
    if not v: return None
    try: return date.fromisoformat(str(v)[:10])
    except ValueError: return None

def _payload(v):
    if not v: return {}
    try: return json.loads(v)
    except Exception: return {}

def _iso(v): return v.isoformat() if v else None

def build_opportunity_pathways_v16c():
    c=connect()
    try:
        market=execute(c,'SELECT market_code,county_name,town_name,market_name,config_json FROM market_registry WHERE market_code=?',(PILOT,)).fetchone()
        if not market: raise RuntimeError('V16A market registry missing')
        members=[str(r[0]) for r in execute(c,'SELECT parcel_id FROM property_market_membership WHERE market_code=? ORDER BY parcel_id',(PILOT,)).fetchall()]
        if len(members)!=EXPECTED_RESIDENTIAL:
            raise RuntimeError(f'membership guard failed: expected {EXPECTED_RESIDENTIAL}, found {len(members)}')
        # Consume V16B current state, not raw source tables.
        states=_rows(c,"""SELECT s.*,l.payload_json,l.evidence_grade
          FROM evidence_current_state s
          LEFT JOIN evidence_ledger l ON l.evidence_key=s.evidence_key
          WHERE s.market_code=? AND s.is_present=1""",(PILOT,))
        changes=_rows(c,"""SELECT * FROM evidence_change_events
          WHERE market_code=? ORDER BY detected_at,change_key""",(PILOT,))
        by_parcel=defaultdict(list)
        for r in states: by_parcel[str(r['parcel_id'])].append(r)
        changes_by_parcel=defaultdict(list)
        for r in changes: changes_by_parcel[str(r['parcel_id'])].append(r)

        today=date.today(); pathway_counts=defaultdict(int); candidates=[]
        for pid in members:
            rows=by_parcel.get(pid,[])
            transfer=[r for r in rows if r.get('evidence_family')=='TRANSFER_TITLE' and r.get('quality_state')=='VALID' and _parse_date(r.get('event_date'))]
            transfer_dates=sorted({_parse_date(r.get('event_date')) for r in transfer if _parse_date(r.get('event_date'))})
            latest=transfer_dates[-1] if transfer_dates else None
            reasons=[]

            # Historical lenses are explicitly research reasons, not seller intent.
            if latest and (today-latest).days >= LONG_GAP_DAYS:
                reasons.append({'pathway':'LONG_RECORDED_TRANSFER_GAP_RESEARCH','basis':'GUARDED_TRANSFER_TITLE','facts':{'latest_valid_recorded_transfer_date':_iso(latest),'gap_years_approx':round((today-latest).days/365.25,1)},'seller_intent':False})
            if len(transfer_dates)>=MIN_VALID_HISTORY:
                reasons.append({'pathway':'MULTI_EVENT_TRANSFER_HISTORY_RESEARCH','basis':'GUARDED_TRANSFER_TITLE','facts':{'distinct_valid_transfer_dates':len(transfer_dates),'latest_valid_recorded_transfer_date':_iso(latest)},'seller_intent':False})
            if latest and (today-latest).days <= RECENT_TITLE_DAYS:
                reasons.append({'pathway':'RECENT_RECORDED_TITLE_ACTIVITY_RESEARCH','basis':'GUARDED_TRANSFER_TITLE','facts':{'latest_valid_recorded_transfer_date':_iso(latest),'days_since_latest':(today-latest).days},'seller_intent':False})
            if not latest:
                reasons.append({'pathway':'NO_VALID_TRANSFER_DATE_RESEARCH_GAP','basis':'GUARDED_TRANSFER_TITLE','facts':{'valid_transfer_dates':0},'seller_intent':False})

            # V16B change events are the operational pathway. None exist at baseline by design.
            factual_changes=[]
            for ch in changes_by_parcel.get(pid,[]):
                factual_changes.append({'change_type':ch.get('change_type'),'evidence_family':ch.get('evidence_family'),'evidence_type':ch.get('evidence_type'),'source':ch.get('source'),'detected_at':ch.get('detected_at')})
            if factual_changes:
                fams=sorted({x['evidence_family'] for x in factual_changes})
                reasons.append({'pathway':'NEW_OR_CHANGED_FACTUAL_EVIDENCE_RESEARCH','basis':'V16B_CHANGE_DETECTION','facts':{'change_event_count':len(factual_changes),'evidence_families':fams},'seller_intent':False})

            for x in reasons: pathway_counts[x['pathway']]+=1
            if reasons:
                candidates.append({'parcel_id':pid,'research_reasons':reasons,'research_reason_count':len(reasons),'contact_authorized':False,'seller_intent_inferred':False})

        # Explainable preview only; no ranking. Keep payload bounded while returning counts for all.
        examples=candidates[:25]
        no_reason=len(members)-len(candidates)
        return {
          'status':'ok','version':VERSION,'mode':MODE,
          'architecture':{'scope':'SUFFOLK_COUNTY_MULTI_MARKET','pilot_market':PILOT,'core_logic_market_agnostic':True,'principle':'BUILD_ONCE_CONFIGURE_BY_MARKET_MEASURE_LOCALLY'},
          'population':{'market_residential_properties':len(members),'properties_with_one_or_more_research_reasons':len(candidates),'properties_with_no_current_research_reason':no_reason,'all_properties_remain_eligible':True},
          'pathways':{'counts':dict(sorted(pathway_counts.items())),'definitions':{
             'LONG_RECORDED_TRANSFER_GAP_RESEARCH':'Latest guarded recorded transfer is approximately 20+ years old; this is not owner tenure or seller intent.',
             'MULTI_EVENT_TRANSFER_HISTORY_RESEARCH':'Three or more distinct valid dated transfer/title observations exist; descriptive history only.',
             'RECENT_RECORDED_TITLE_ACTIVITY_RESEARCH':'Latest guarded recorded transfer/title activity is within approximately 3 years; factual activity only.',
             'NO_VALID_TRANSFER_DATE_RESEARCH_GAP':'No valid dated transfer observation is available after quality guards; a research gap, not a seller signal.',
             'NEW_OR_CHANGED_FACTUAL_EVIDENCE_RESEARCH':'V16B detected new/changed/reappeared/missing factual evidence after baseline; requires interpretation before any action.'}},
          'change_memory':{'v16b_change_events_available':len(changes),'properties_with_change_events':len(changes_by_parcel)},
          'preview':{'ordering':'PARCEL_ID_ONLY_NOT_PRIORITY_RANKING','returned':len(examples),'properties':examples},
          'behavior':{'database_writes':0,'seller_scoring':False,'seller_probability':False,'seller_intent_inferred':False,'watch_state_touched':False,'investigate_state_touched':False,'opportunity_state_touched':False,'outreach_touched':False,'contact_authorized':False,'price_floor':False,'luxury_floor':False,'property_size_floor':False,'geographic_prestige_requirement':False},
          'interpretation_limits':['Research pathway does not mean seller.','Recorded transfer gap does not prove owner tenure.','Property context is not seller intent.','No current research reason does not remove a property from the universe.','Contact remains downstream of ownership verification and Contact Governor.'],
          'next_locked_step':'V16D_OPERATIONAL_INVESTIGATION_STATE_AND_EXPLAINABLE_QUEUE_AFTER_V16C_VERIFICATION'
        }
    finally:
        c.close()
