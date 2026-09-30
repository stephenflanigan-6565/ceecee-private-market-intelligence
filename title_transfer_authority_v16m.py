#!/usr/bin/env python3
"""V16M — authoritative Suffolk document-code resolver and factual event-family census.
Read-only. Meanings come from Suffolk County TaxParcelTransferHistory DOCCODE coded-value domain.
Event families are PMI organizational categories only; they do not infer seller intent.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from db import connect, execute

VERSION='V16M'
MODE='READ_ONLY_AUTHORITATIVE_DOCUMENT_CODE_RESOLUTION'
MARKET='WESTHAMPTON_BEACH_NY'
SOURCE='Suffolk TaxParcelTransferHistory'
AUTHORITY_URL='https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/FeatureServer/0?f=pjson'

# Exact coded-value names published by Suffolk County in the DOCCODE domain.
SUFFOLK_CODES={
'ACD':'ASSIGNMENT OF COLLATERAL','ADD':'ADMINISTRATOR','ADM':'ADMINISTRATOR','AGT':'AGREEMENT',
'AHS':'AFFIDAVIT OF HEIRSHIP','APD':'APPROPRIATION','ARR':'ASSESSORS REQ RESOLUTION','BAG':'BOUNDARY AGREEMENT',
'BSD':'BARGAIN AND SALE','CAI':'COURT ACTION INDEX','CLD':'COLLATERAL','COA':'CERTIFICATE OF ABANDONE',
'COC':'CERTIFICATE OF CORRECTION','CRS':'COUNTY RESOLUTION','CSD':'CONSERVATOR','CTC':'CERTIFICATE TO CLERK',
'CTF':'CERTIFICATE','CTK':'COUNTY TAKING','DCL':'DECLARATION','DRD':'DEDICATION & RELEASE','ESM':'EASEMENT',
'EXD':'EXECUTOR','FCD':'FORECLOSURE','FTK':'FEDERAL TAKING','GRT':'GRANT','IAC':'INST OF ABANDONE OF CLAIM',
'LAG':'LEASE AGREEMENT','LTP':'LETTER OF PATENT','LTR':'LETTER OF REDEMPTION','LWT':'LAST WILL AND TESTAMENT',
'MGD':'MORTGAGE','MSC':'MISCELLANEOUS','OAG':'OWNERSHIP AGREEMENT','PAT':'PATENT','POA':'POWER OF ATTORNEY',
'PRB':'PROBATE','PTD':'PARTITION','QCD':'QUITCLAIM','RCD':'RELEASE OF COLLATERAL','RRD':'RECEIPT AND RELEASE',
'RVD':'REVERTER','SAT':'SATISFACTION OF MORTGAGE','SCA':'SURROGATE COURT ACTION','SCO':'SUPREME COURT ORDER',
'SHD':'SHERIFF','STK':'STATE TAKING','STM':'STATEMENT IDENTIFYING RP','TRD':'TRUST/TRUSTEES','TRS':'TOWN RESOLUTION',
'TSC':'TAX SALE CANCELLATION','TST':'TESTAMENTARY','TTK':'TOWN TAKING','TXD':'TAX','UNK':'UNKNOWN','URD':'UNRECORDED',
'VRS':'VILLAGE RESOLUTION','VTK':'VILLAGE TAKING','WRD':'WARRANTY'}

# Conservative organizational families. These are not motivation or seller labels.
FAMILY={
'BSD':'CONVEYANCE_DEED','QCD':'CONVEYANCE_DEED','WRD':'CONVEYANCE_DEED','GRT':'CONVEYANCE_DEED','SHD':'CONVEYANCE_DEED',
'EXD':'ESTATE_FIDUCIARY','ADD':'ESTATE_FIDUCIARY','ADM':'ESTATE_FIDUCIARY','CSD':'ESTATE_FIDUCIARY','PRB':'ESTATE_FIDUCIARY','LWT':'ESTATE_FIDUCIARY','TST':'ESTATE_FIDUCIARY','AHS':'ESTATE_FIDUCIARY','SCA':'ESTATE_FIDUCIARY',
'FCD':'COURT_FORECLOSURE_TAX','SCO':'COURT_FORECLOSURE_TAX','CAI':'COURT_FORECLOSURE_TAX','TXD':'COURT_FORECLOSURE_TAX','TSC':'COURT_FORECLOSURE_TAX','LTR':'COURT_FORECLOSURE_TAX',
'MGD':'FINANCING_COLLATERAL','SAT':'FINANCING_COLLATERAL','ACD':'FINANCING_COLLATERAL','CLD':'FINANCING_COLLATERAL','RCD':'FINANCING_COLLATERAL',
'ESM':'PROPERTY_RIGHTS_AGREEMENT','BAG':'PROPERTY_RIGHTS_AGREEMENT','AGT':'PROPERTY_RIGHTS_AGREEMENT','DCL':'PROPERTY_RIGHTS_AGREEMENT','DRD':'PROPERTY_RIGHTS_AGREEMENT','LAG':'PROPERTY_RIGHTS_AGREEMENT','OAG':'PROPERTY_RIGHTS_AGREEMENT','RRD':'PROPERTY_RIGHTS_AGREEMENT','IAC':'PROPERTY_RIGHTS_AGREEMENT','RVD':'PROPERTY_RIGHTS_AGREEMENT',
'APD':'GOVERNMENT_TAKING_RESOLUTION','CTK':'GOVERNMENT_TAKING_RESOLUTION','FTK':'GOVERNMENT_TAKING_RESOLUTION','STK':'GOVERNMENT_TAKING_RESOLUTION','TTK':'GOVERNMENT_TAKING_RESOLUTION','VTK':'GOVERNMENT_TAKING_RESOLUTION','CRS':'GOVERNMENT_TAKING_RESOLUTION','TRS':'GOVERNMENT_TAKING_RESOLUTION','VRS':'GOVERNMENT_TAKING_RESOLUTION','ARR':'GOVERNMENT_TAKING_RESOLUTION',
'CTC':'ADMINISTRATIVE_RECORD','CTF':'ADMINISTRATIVE_RECORD','COA':'ADMINISTRATIVE_RECORD','COC':'ADMINISTRATIVE_RECORD','STM':'ADMINISTRATIVE_RECORD','POA':'ADMINISTRATIVE_RECORD','MSC':'ADMINISTRATIVE_RECORD','UNK':'UNRESOLVED_SOURCE','URD':'UNRESOLVED_SOURCE',
'PAT':'OTHER_TITLE_INSTRUMENT','LTP':'OTHER_TITLE_INSTRUMENT','PTD':'OTHER_TITLE_INSTRUMENT','TRD':'OTHER_TITLE_INSTRUMENT'}

def _rows(cur):
    cols=[d[0] for d in cur.description]; return [dict(zip(cols,r)) for r in cur.fetchall()]

def _date(v):
    if v in (None,''): return None
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    try: return date.fromisoformat(str(v)[:10])
    except Exception: return None

def build_title_transfer_authority_v16m():
    c=connect()
    try:
        members={str(r[0]) for r in execute(c,'SELECT parcel_id FROM property_market_membership WHERE market_code=?',(MARKET,)).fetchall()}
        raw=_rows(execute(c,'SELECT parcel_id, record_date, document_date, entry_date, document_number, document_code, history_sequence FROM transfers WHERE source=?',(SOURCE,)))
    finally: c.close()
    rows=[r for r in raw if str(r.get('parcel_id')) in members]
    today=date.today(); cut365=today-timedelta(days=365); cut1095=today-timedelta(days=1095)
    by_code=Counter(); parcels={}; r365=Counter(); r1095=Counter(); family_counts=Counter(); family_parcels={}
    unresolved_records=0; missing_records=0
    for r in rows:
        code=str(r.get('document_code') or '').strip().upper()
        if not code: code='[MISSING]'; missing_records+=1
        by_code[code]+=1; parcels.setdefault(code,set()).add(str(r.get('parcel_id')))
        meaning=SUFFOLK_CODES.get(code)
        fam=FAMILY.get(code,'UNRESOLVED_SOURCE') if meaning else 'UNRESOLVED_SOURCE'
        family_counts[fam]+=1; family_parcels.setdefault(fam,set()).add(str(r.get('parcel_id')))
        if not meaning: unresolved_records+=1
        d=_date(r.get('record_date')) or _date(r.get('document_date')) or _date(r.get('entry_date'))
        if d and d<=today:
            if d>=cut365: r365[code]+=1
            if d>=cut1095: r1095[code]+=1
    codes=[]
    for code,n in by_code.most_common():
        meaning=SUFFOLK_CODES.get(code)
        codes.append({'document_code':code,'official_meaning':meaning or ('MISSING_SOURCE_CODE' if code=='[MISSING]' else 'UNRESOLVED_SOURCE_CODE'),
                      'authority':'SUFFOLK_COUNTY_DOCCODE_DOMAIN' if meaning else None,
                      'event_family':FAMILY.get(code,'UNRESOLVED_SOURCE') if meaning else 'UNRESOLVED_SOURCE',
                      'records':n,'distinct_properties':len(parcels.get(code,set())),'records_last_365_days':r365.get(code,0),'records_last_3_years':r1095.get(code,0),'seller_intent':False})
    families=[]
    for fam,n in family_counts.most_common():
        families.append({'event_family':fam,'records':n,'distinct_properties':len(family_parcels.get(fam,set())),'seller_intent':False})
    present_codes=[c for c in by_code if c!='[MISSING]']
    resolved_present=sum(1 for c in present_codes if c in SUFFOLK_CODES)
    return {'status':'ok','version':VERSION,'mode':MODE,'generated_at':datetime.now(timezone.utc).isoformat(),'market_code':MARKET,
      'authority':{'source':'Suffolk County TaxParcelTransferHistory FeatureServer DOCCODE coded-value domain','url':AUTHORITY_URL,'policy':'Official meanings are copied from Suffolk coded values; PMI event families are organizational only and do not imply seller intent.'},
      'population':{'market_properties':len(members),'transfer_records':len(rows)},
      'resolution':{'distinct_present_nonmissing_codes':len(present_codes),'resolved_present_codes':resolved_present,'unresolved_present_codes':len(present_codes)-resolved_present,'missing_code_records':missing_records,'unresolved_records_including_missing':unresolved_records},
      'document_codes':codes,'event_families':families,
      'guards':{'database_writes':False,'investigate_state_touched':False,'seller_intent_inferred':False,'seller_scoring':False,'contact_authorized':False,'outreach_touched':False}}
