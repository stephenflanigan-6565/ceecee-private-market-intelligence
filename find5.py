#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from find4 import build_find4

VERSION='FIND5C'
PARCEL_URL='https://gis.southamptontownny.gov/gisserver/rest/services/DataServices/TaxParcels/MapServer/0/query'
ZONING_URL='https://gis.southamptontownny.gov/gisserver/rest/services/DataServices/LandManager/MapServer/41/query'

def _get(url, params, timeout=12):
    q=urllib.parse.urlencode(params)
    req=urllib.request.Request(url+'?'+q, headers={'User-Agent':'PMI-Research/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def _parcel_by_sctm(parcel_id, address=None):
    # Live FIND5P contract proved SCTM is the parcel layer's 19-digit Suffolk tax-map key.
    raw=''.join(ch for ch in str(parcel_id or '') if ch.isdigit())
    diag={'query_field':'SCTM','query_form':raw,'address_cross_check_only':address}
    if len(raw)!=19:
        return None,'INVALID_PMI_SCTM_FORM',diag
    safe=raw.replace("'","''")
    data=_get(PARCEL_URL, {
        'f':'json',
        'where':f"SCTM='{safe}'",
        'outFields':'OBJECTID,DSBL,PARCEL_ID,CIVIC,ST_ADDRS,SCTM,X_COORD,Y_COORD',
        'returnGeometry':'true',
        'outSR':'2263'
    })
    if data.get('error'):
        diag['service_error']=data.get('error')
        return None,'SCTM_QUERY_REJECTED',diag
    fs=data.get('features') or []
    diag['match_count']=len(fs)
    if len(fs)==1:
        a=fs[0].get('attributes') or {}
        diag['returned_sctm']=a.get('SCTM')
        diag['returned_st_addrs']=a.get('ST_ADDRS')
        diag['address_exact_cross_check']=(str(a.get('ST_ADDRS') or '').strip().upper()==str(address or '').strip().upper())
        return fs[0],None,diag
    if len(fs)>1:
        return None,'MULTIPLE_SCTM_MATCHES',diag
    return None,'NO_SCTM_MATCH',diag

def _zone_for_parcel(feature):
    geom=feature.get('geometry')
    if not geom: return [],'PARCEL_GEOMETRY_MISSING'
    # ArcGIS polygon geometry can be supplied directly for spatial intersection.
    data=_get(ZONING_URL, {'f':'json','where':'1=1','outFields':'CODE,ZONE,DESCRIPT,DIM_REG,LL_PATH',
                           'returnGeometry':'false','geometry':json.dumps(geom),
                           'geometryType':'esriGeometryPolygon','inSR':'2263','spatialRel':'esriSpatialRelIntersects'})
    fs=data.get('features') or []
    zones=[]
    for z in fs:
        a=z.get('attributes') or {}
        zones.append({k:a.get(k) for k in ('CODE','ZONE','DESCRIPT','DIM_REG','LL_PATH')})
    return zones, None if zones else 'NO_WHB_ZONING_INTERSECTION'

def _sample(profiles):
    # Deterministic evidence-family cross-section, not ranking.
    buckets={}
    for p in profiles:
        lr=p.get('land_route')
        if not lr: continue
        fam=lr.get('causal_family') or 'UNKNOWN'
        rel='|'.join(sorted(lr.get('observed_relationships') or []))
        key=(lr.get('state'),fam,rel)
        buckets.setdefault(key,[]).append(p)
    chosen=[]
    for key in sorted(buckets):
        chosen.extend(sorted(buckets[key],key=lambda x:x.get('parcel_id',''))[:2])
    # cap validation traffic while preserving family diversity
    return chosen[:12]

def build_find5():
    f4=build_find4(include_all_profiles=True)
    profiles=f4.get('profiles') or []
    sample=_sample(profiles)
    results=[]; outcomes=Counter(); zone_counts=Counter()
    for p in sample:
        lr=p.get('land_route') or {}
        rec={'parcel_id':p.get('parcel_id'),'property_address':p.get('property_address'),
             'find4_state':p.get('current_find_state'),'causal_family':lr.get('causal_family'),
             'observed_relationships':lr.get('observed_relationships') or [],
             'seller_intent':'UNKNOWN','contact_authorized':False}
        try:
            parcel,err,diag=_parcel_by_sctm(p.get('parcel_id'),p.get('property_address'))
            rec['parcel_identity_diagnostic']=diag
            if err:
                rec['adapter_state']=err; outcomes[err]+=1
            else:
                a=parcel.get('attributes') or {}
                rec['town_parcel_match']={k:a.get(k) for k in ('DSBL','SCTM','ST_ADDRS','PARCEL_ID')}
                zones,zerr=_zone_for_parcel(parcel)
                rec['zoning']=zones
                if zerr:
                    rec['adapter_state']=zerr; outcomes[zerr]+=1
                else:
                    rec['adapter_state']='PARCEL_AND_ZONING_RESOLVED'; outcomes[rec['adapter_state']]+=1
                    for z in zones: zone_counts[str(z.get('ZONE') or z.get('CODE') or 'UNKNOWN')]+=1
        except Exception as e:
            rec['adapter_state']='SOURCE_REQUEST_ERROR'; rec['error_type']=type(e).__name__; rec['error']=str(e)[:300]; outcomes['SOURCE_REQUEST_ERROR']+=1
        results.append(rec)
    resolved=outcomes.get('PARCEL_AND_ZONING_RESOLVED',0)
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_TARGETED_SITE_USE_SOURCE_ADAPTER_VALIDATION',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'VALIDATE_AUTHORITATIVE_TOWN_PARCEL_TO_WHB_ZONING_JOIN_BEFORE_SCALING_TO_ALL_FIND4_LAND_ROUTES',
      'source_contract':{
        'parcel_source':'Town of Southampton DataServices/TaxParcels MapServer layer 0',
        'zoning_source':'Town of Southampton DataServices/LandManager MapServer layer 41 — Westhampton Beach',
        'parcel_match':'EXACT_SCTM_19_DIGIT_IDENTITY_PROVEN_BY_LIVE_FIND5P_CONTRACT; ADDRESS_CROSS_CHECK_ONLY',
        'zoning_match':'SPATIAL_INTERSECTION_OF_AUTHORITATIVE_TOWN_PARCEL_GEOMETRY',
        'owner_fields_requested':False},
      'sample_policy':'DETERMINISTIC_UP_TO_2_PER_FIND4_LAND_STATE_CAUSAL_FAMILY_RELATIONSHIP_COMBINATION_MAX_12',
      'summary':{'find4_unified_profiles':len(profiles),'find4_land_profiles':sum(1 for p in profiles if p.get('land_route')),
                 'validation_sample':len(sample),'adapter_outcomes':dict(outcomes),'zones_observed':dict(zone_counts),
                 'all_sample_records_resolved':bool(sample) and resolved==len(sample),'sctm_primary_key_validation':True},
      'results':results,
      'interpretation_policy':{
        'zoning_fact_does_not_equal_redevelopment_permission':True,
        'zoning_fact_does_not_equal_subdivision_permission':True,
        'site_use_fact_may_strengthen_weaken_or_kill_only_the_relevant_route':True,
        'route_kill_never_equals_property_kill':True,'seller_intent_inferred':False,
        'missing_or_failed_source_match_is_unknown_not_rejection':True},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,
                'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,
                'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'SCALE VALIDATED SCTM_PARCEL_TO_ZONING JOIN ACROSS ALL 153 FIND4 LAND ROUTES; THEN TEST ZONING_AND_SITE_CONTEXT AS CAUSAL EVIDENCE WITHOUT INFERRING ENTITLEMENT'
    }

if __name__=='__main__':
    print(json.dumps(build_find5(),indent=2,sort_keys=True))
