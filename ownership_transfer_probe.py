#!/usr/bin/env python3
"""V15F read-only Suffolk ownership + current-transfer coverage probe.
No owner names are returned by the public diagnostic endpoint.
No database writes are performed.
"""
from datetime import datetime, timezone
import json, urllib.parse, urllib.request
from db import connect, execute, backend

BASE='https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData'
OWNER=BASE+'/TaxParcelOwner/FeatureServer/0/query'
TRANSFER=BASE+'/TaxParcelTransferCurrent/FeatureServer/0/query'
DISTRICT_PREFIX='0905'
PAGE=1000

def utc(): return datetime.now(timezone.utc).isoformat()

def fetch(url, params):
    u=url+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(u,headers={'User-Agent':'Private-Market-Intelligence/15F'})
    with urllib.request.urlopen(req,timeout=90) as r:
        data=json.load(r)
    if 'error' in data:
        raise RuntimeError(data['error'])
    return data

def fetch_all(url, fields):
    out=[]; offset=0
    while True:
        data=fetch(url,{
            'where':f"PARCELID LIKE '{DISTRICT_PREFIX}%'",
            'outFields':fields,
            'returnGeometry':'false','resultOffset':offset,
            'resultRecordCount':PAGE,'orderByFields':'PARCELID','f':'json'
        })
        feats=data.get('features',[])
        out.extend(x.get('attributes',{}) for x in feats)
        if len(feats)<PAGE and not data.get('exceededTransferLimit'):
            break
        if not feats: break
        offset += len(feats)
    return out

def probe():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id FROM properties WHERE district=? AND active=1",('0905',)).fetchall()
        canonical={str(r[0]) for r in rows}
    finally:
        c.close()

    owners=fetch_all(OWNER,'PARCELID,FIRSTNAME,LASTNAME,OWNERNAME')
    transfers=fetch_all(TRANSFER,'PARCELID,TRANSHISSEQ,RECORDDATE,DOCNUM,DOCCODE,SALEDATE,SALEPRICE')

    owner_pids={str(a.get('PARCELID')) for a in owners if a.get('PARCELID') in canonical}
    transfer_pids={str(a.get('PARCELID')) for a in transfers if a.get('PARCELID') in canonical}
    owner_outside=sum(1 for a in owners if a.get('PARCELID') not in canonical)
    transfer_outside=sum(1 for a in transfers if a.get('PARCELID') not in canonical)
    owner_missing=sorted(canonical-owner_pids)
    transfer_missing=sorted(canonical-transfer_pids)

    # No PII in public diagnostics: samples are parcel IDs only.
    return {
      'status':'ok','mode':'READ_ONLY_OWNERSHIP_TRANSFER_PROBE','generated_at':utc(),
      'database_backend':backend(),'district':'0905','canonical_active_parcels':len(canonical),
      'owner_source':'Suffolk County TaxParcelOwner','owner_records_fetched':len(owners),
      'parcels_with_current_owner_record':len(owner_pids),
      'parcels_without_current_owner_record':len(owner_missing),
      'owner_records_outside_canonical_universe':owner_outside,
      'current_transfer_source':'Suffolk County TaxParcelTransferCurrent',
      'current_transfer_records_fetched':len(transfers),
      'parcels_with_current_transfer_record':len(transfer_pids),
      'parcels_without_current_transfer_record':len(transfer_missing),
      'transfer_records_outside_canonical_universe':transfer_outside,
      'missing_owner_sample_parcel_ids':owner_missing[:10],
      'missing_transfer_sample_parcel_ids':transfer_missing[:10],
      'owner_names_exposed_in_response':False,
      'database_writes':0,'property_data_touched':False,'ownership_data_touched':False,
      'transfer_data_touched':False,'seller_scoring_touched':False,
      'opportunity_data_touched':False,'outreach_touched':False
    }
