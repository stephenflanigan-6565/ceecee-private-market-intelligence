#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from find7 import build_find7
from find5 import _parcel_by_sctm, ZONING_URL, _post

VERSION='FIND8S'
GEOM_INTERSECT='https://gis.southamptontownny.gov/gisserver/rest/services/Utilities/Geometry/GeometryServer/intersect'

def _ring_signed_area(ring):
    if not ring or len(ring)<3: return 0.0
    s=0.0
    for i,p in enumerate(ring):
        q=ring[(i+1)%len(ring)]
        s += float(p[0])*float(q[1])-float(q[0])*float(p[1])
    return s/2.0

def _polygon_area(geom):
    # Geometry is projected in NY State Plane feet (EPSG:2263). Ring orientation
    # preserves holes; absolute signed total yields square feet.
    rings=(geom or {}).get('rings') or []
    return abs(sum(_ring_signed_area(r) for r in rings))

def _zones_with_geometry(parcel_geom):
    data=_post(ZONING_URL, {
      'f':'json','where':'1=1','outFields':'OBJECTID,CODE,ZONE,DESCRIPT,DIM_REG,LL_PATH',
      'returnGeometry':'true','outSR':'2263','geometry':json.dumps(parcel_geom),
      'geometryType':'esriGeometryPolygon','inSR':'2263','spatialRel':'esriSpatialRelIntersects'})
    if data.get('error'): return [], 'ZONING_GEOMETRY_QUERY_REJECTED', data.get('error')
    fs=data.get('features') or []
    return fs, (None if fs else 'NO_WHB_ZONING_INTERSECTION'), None

def _with_sr(geom):
    # GeometryServer operations are stricter than layer spatial filters: embed
    # the coordinate system in each geometry rather than relying only on sr=.
    g=json.loads(json.dumps(geom or {}))
    g['spatialReference']={'wkid':2263}
    return g

def _intersect(parcel_geom, zone_geom):
    pg=_with_sr(parcel_geom)
    zg=_with_sr(zone_geom)
    payload={
      'f':'json','sr':'2263',
      'geometries':json.dumps({'geometryType':'esriGeometryPolygon','geometries':[pg]}, separators=(',',':')),
      'geometry':json.dumps({'geometryType':'esriGeometryPolygon','geometry':zg}, separators=(',',':'))}
    data=_post(GEOM_INTERSECT, payload)
    if data.get('error'):
        return None, {'service_error':data.get('error'),
                      'geometry_contract':'ESRI_DOCUMENTED_GEOMETRY_ARRAY_PLUS_WRAPPED_SINGLE_POLYGON_WKID_2263'}
    gs=data.get('geometries') or []
    return (gs[0] if gs else None), None

def build_find8():
    f7=build_find7(include_all_profiles=True)
    targets=[]
    for p in f7.get('profiles') or []:
        ctx=p.get('authoritative_site_use_context') or {}
        flags=ctx.get('flags') or []
        if ('MULTI_ZONE_INTERSECTION_REQUIRES_GEOMETRIC_APPLICABILITY_REVIEW' in flags or
            'CONSERVATION_OR_OPEN_SPACE_CONSTRAINT_SIGNAL' in flags):
            targets.append(p)
    results=[]; outcomes=Counter(); zone_share_states=Counter()
    for p in targets:
        rec={'parcel_id':p.get('parcel_id'),'property_address':p.get('property_address'),
             'find7_state':p.get('current_find_state'),'seller_intent':'UNKNOWN','contact_authorized':False}
        try:
            parcel,err,diag=_parcel_by_sctm(p.get('parcel_id'),p.get('property_address'))
            if err:
                rec['adapter_state']=err; rec['parcel_identity_diagnostic']=diag; outcomes[err]+=1; results.append(rec); continue
            pg=parcel.get('geometry') or {}
            pa=_polygon_area(pg)
            rec['parcel_area_geometry_sqft']=round(pa,2) if pa else None
            zfs,zerr,zdetail=_zones_with_geometry(pg)
            if zerr:
                rec['adapter_state']=zerr; rec['source_error']=zdetail; outcomes[zerr]+=1; results.append(rec); continue
            shares=[]; total_intersection=0.0; failed=False
            for zf in zfs:
                za=zf.get('attributes') or {}; zg=zf.get('geometry') or {}
                ig,ierr=_intersect(pg,zg)
                if ierr:
                    failed=True
                    shares.append({'zone':za.get('ZONE') or za.get('CODE'),'state':'INTERSECTION_UNKNOWN','error':ierr})
                    continue
                ia=_polygon_area(ig) if ig else 0.0; total_intersection+=ia
                shares.append({'zone':za.get('ZONE') or za.get('CODE'),'code':za.get('CODE'),
                               'description':za.get('DESCRIPT'),'dimensional_regime':za.get('DIM_REG'),
                               'intersection_sqft':round(ia,2),
                               'parcel_area_share':round(ia/pa,6) if pa else None})
            rec['zone_area_shares']=shares
            if failed:
                rec['adapter_state']='PARTIAL_GEOMETRY_RESOLUTION'
                rec['geometry_evidence_state']='ZONE_AREA_SHARE_PARTIAL_UNKNOWN'
            else:
                rec['adapter_state']='GEOMETRIC_ZONE_APPLICABILITY_RESOLVED'
                rec['geometry_evidence_state']='ZONE_AREA_SHARE_RESOLVED'
                rec['intersection_share_sum']=round(total_intersection/pa,6) if pa else None
            # Geometry share is factual spatial context only. It does not establish legal use/buildability.
            pc=sum((x.get('parcel_area_share') or 0) for x in shares if str(x.get('zone') or '').upper()=='PC')
            if pc:
                rec['conservation_geometry_context']={'pc_zone_parcel_share':round(pc,6),
                  'non_pc_geometric_remainder_share':round(max(0.0,1.0-pc),6),
                  'interpretation':'GEOMETRIC_REMAINDER_ONLY_NOT_LEGAL_BUILDABLE_AREA'}
            rec['next_best_property_question']='WHAT_DO_CURRENT_LAWFUL_USE_DIMENSIONAL_ENVIRONMENTAL_AND_IMPROVEMENT_FACTS_ALLOW_OR_CONSTRAIN_WITHIN_THE_GEOMETRIC_ZONE_PATTERN'
            outcomes[rec['adapter_state']]+=1; zone_share_states[rec['geometry_evidence_state']]+=1
        except Exception as e:
            rec['adapter_state']='SOURCE_REQUEST_ERROR'; rec['geometry_evidence_state']='SOURCE_REQUEST_UNKNOWN'
            rec['error_type']=type(e).__name__; rec['error']=str(e)[:300]
            outcomes['SOURCE_REQUEST_ERROR']+=1; zone_share_states['SOURCE_REQUEST_UNKNOWN']+=1
        results.append(rec)
    resolved=outcomes.get('GEOMETRIC_ZONE_APPLICABILITY_RESOLVED',0)
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_TARGETED_ZONE_GEOMETRIC_APPLICABILITY_ESRI_WRAPPED_GEOMETRY_REPAIR',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'RESOLVE_HOW_MUCH_OF_EACH_SPECIALIZED_FIND7_PARCEL_GEOMETRICALLY_INTERSECTS_EACH_ZONING_POLYGON_WITHOUT_INFERRING_LAWFUL_USE_BUILDABILITY_SUBDIVISION_YIELD_OR_ENTITLEMENT',
      'source_checkpoint':{'find7':f7.get('version'),'unified_property_profiles':len(f7.get('profiles') or [])},
      'scope':{'target_policy':'FIND7_MULTI_ZONE_OR_CONSERVATION_SIGNAL_ONLY','targeted_properties':len(targets),'results':len(results)},
      'summary':{'adapter_outcomes':dict(outcomes),'geometry_evidence_states':dict(zone_share_states),
                 'geometric_zone_applicability_resolved':resolved,
                 'all_targets_resolved':bool(targets) and resolved==len(targets)},
      'results':results,
      'interpretation_policy':{'zone_area_share_is_geometric_fact_only':True,'zoning_not_entitlement':True,
        'non_conservation_remainder_not_legal_buildable_area':True,'parcel_intersection_not_proof_of_lawful_use':True,
        'multi_zone_not_automatic_opportunity':True,'constraint_not_automatic_route_kill':True,
        'route_kill_never_equals_property_kill':True,'seller_intent_inferred':False,'unknown_valid_state':True},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,
        'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,
        'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'INTEGRATE_GEOMETRIC_ZONE_APPLICABILITY_INTO_FIND7_CHASSIS; THEN SELECT_ONE_AUTHORITATIVE_PROPERTY_FORM_OR_CONSTRAINT_FACT_BY_INFORMATION_VALUE; DO_NOT_INFER_ENTITLEMENT'}

if __name__=='__main__':
    print(json.dumps(build_find8(),indent=2,sort_keys=True))
