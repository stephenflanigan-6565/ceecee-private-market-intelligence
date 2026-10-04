#!/usr/bin/env python3
import json, time
from collections import Counter
from datetime import datetime, timezone
from find4 import build_find4
from find5 import _parcel_by_sctm, _zone_for_parcel

VERSION='FIND6'

def _interpret_zones(zones):
    codes=sorted({str((z.get('ZONE') or z.get('CODE') or '')).strip() for z in zones if (z.get('ZONE') or z.get('CODE'))})
    descriptions=sorted({str(z.get('DESCRIPT') or '').strip() for z in zones if z.get('DESCRIPT')})
    dims=sorted({str(z.get('DIM_REG') or '').strip() for z in zones if z.get('DIM_REG') is not None})
    if not codes:
        return 'ZONING_UNKNOWN', [], ['ZONING_NOT_RESOLVED']
    flags=[]
    if len(codes)>1:
        flags.append('MULTI_ZONE_INTERSECTION_REQUIRES_GEOMETRIC_APPLICABILITY_REVIEW')
    if any(c in {'PC'} for c in codes) or any('CONSERV' in d.upper() or 'OPEN SPACE' in d.upper() for d in descriptions):
        flags.append('CONSERVATION_OR_OPEN_SPACE_CONSTRAINT_SIGNAL')
    if any(c.startswith('B') or c in {'HC'} for c in codes):
        flags.append('COMMERCIAL_OR_HAMLET_MIXED_USE_CONTEXT')
    if any(c.startswith('MF') for c in codes):
        flags.append('MULTIFAMILY_CONTEXT')
    if flags:
        return 'SITE_USE_CONTEXT_COMPLICATES_OR_SPECIALIZES_ROUTE', codes, flags
    return 'SINGLE_ZONE_CONTEXT_RESOLVED', codes, ['ZONING_CONTEXT_RESOLVED_NO_ENTITLEMENT_INFERENCE']

def build_find6():
    f4=build_find4(include_all_profiles=True)
    land=[p for p in (f4.get('profiles') or []) if p.get('land_route')]
    results=[]
    outcomes=Counter(); zones=Counter(); evidence_states=Counter(); causal=Counter()
    for p in land:
        lr=p.get('land_route') or {}
        rec={
          'parcel_id':p.get('parcel_id'),
          'property_address':p.get('property_address'),
          'find4_state':p.get('current_find_state'),
          'land_causal_family':lr.get('causal_family'),
          'land_route_state':lr.get('state'),
          'observed_relationships':lr.get('observed_relationships') or [],
          'seller_intent':'UNKNOWN','contact_authorized':False
        }
        try:
            parcel,err,diag=_parcel_by_sctm(p.get('parcel_id'),p.get('property_address'))
            rec['parcel_identity']={'state':'RESOLVED' if not err else err,
                                    'query_field':'SCTM',
                                    'match_count':diag.get('match_count'),
                                    'returned_sctm':diag.get('returned_sctm')}
            if err:
                rec['adapter_state']=err
                rec['site_use_evidence_state']='SOURCE_IDENTITY_UNKNOWN'
                rec['site_use_flags']=['MISSING_SITE_USE_EVIDENCE_IS_UNKNOWN_NOT_REJECTION']
                outcomes[err]+=1; evidence_states[rec['site_use_evidence_state']]+=1
            else:
                a=parcel.get('attributes') or {}
                rec['town_parcel']={k:a.get(k) for k in ('DSBL','SCTM','ST_ADDRS','PARCEL_ID')}
                z,zerr=_zone_for_parcel(parcel)
                if zerr:
                    rec['adapter_state']=zerr
                    rec['site_use_evidence_state']='ZONING_UNKNOWN'
                    rec['site_use_flags']=['MISSING_SITE_USE_EVIDENCE_IS_UNKNOWN_NOT_REJECTION']
                    outcomes[zerr]+=1; evidence_states[rec['site_use_evidence_state']]+=1
                else:
                    rec['adapter_state']='PARCEL_AND_ZONING_RESOLVED'
                    state,codes,flags=_interpret_zones(z)
                    rec['site_use_evidence_state']=state
                    rec['site_use_flags']=flags
                    rec['zoning']=[{k:x.get(k) for k in ('CODE','ZONE','DESCRIPT','DIM_REG')} for x in z]
                    outcomes['PARCEL_AND_ZONING_RESOLVED']+=1
                    evidence_states[state]+=1
                    for c in codes: zones[c]+=1
            causal[str(lr.get('causal_family') or 'UNKNOWN')]+=1
        except Exception as e:
            rec['adapter_state']='SOURCE_REQUEST_ERROR'
            rec['site_use_evidence_state']='SOURCE_REQUEST_UNKNOWN'
            rec['site_use_flags']=['SOURCE_FAILURE_IS_UNKNOWN_NOT_REJECTION']
            rec['error_type']=type(e).__name__
            rec['error']=str(e)[:240]
            outcomes['SOURCE_REQUEST_ERROR']+=1
            evidence_states['SOURCE_REQUEST_UNKNOWN']+=1
        results.append(rec)

    resolved=outcomes.get('PARCEL_AND_ZONING_RESOLVED',0)
    return {
      'status':'ok','version':VERSION,
      'mode':'READ_ONLY_FULL_FIND4_LAND_SITE_USE_CONTEXT_SCALE',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'SCALE_THE_PROVEN_SCTM_TO_TOWN_PARCEL_TO_WHB_ZONING_ADAPTER_ACROSS_ALL_FIND4_LAND_ROUTES_AND_CLASSIFY_SITE_USE_CONTEXT_WITHOUT_INFERRING_ENTITLEMENT',
      'source_contract':{
        'parcel_identity':'EXACT_19_DIGIT_SCTM',
        'parcel_source':'Town of Southampton DataServices/TaxParcels MapServer layer 0',
        'zoning_source':'Town of Southampton DataServices/LandManager MapServer layer 41 — Westhampton Beach',
        'zoning_join':'FORM_POST_SPATIAL_INTERSECTION_OF_TOWN_PARCEL_GEOMETRY',
        'owner_fields_consumed':False},
      'scope':{
        'find4_unified_profiles':len(f4.get('profiles') or []),
        'find4_land_routes':len(land),
        'scaled_land_routes':len(results),
        'complete_population_coverage':len(results)==len(land)},
      'summary':{
        'adapter_outcomes':dict(outcomes),
        'site_use_evidence_states':dict(evidence_states),
        'zones_observed':dict(zones),
        'land_causal_families':dict(causal),
        'parcel_and_zoning_resolved':resolved,
        'resolution_rate':round(resolved/len(results),6) if results else None},
      'profiles':results,
      'interpretation_policy':{
        'zoning_is_site_use_context_not_entitlement':True,
        'multi_zone_is_complexity_not_automatic_opportunity':True,
        'conservation_open_space_is_constraint_signal_not_automatic_route_kill':True,
        'commercial_or_multifamily_context_is_specialization_not_seller_signal':True,
        'missing_source_evidence_is_unknown_not_rejection':True,
        'route_kill_never_equals_property_kill':True,
        'seller_intent_inferred':False},
      'database_writes':0,
      'guards':{
        'database_writes':False,'external_calls':True,'external_calls_read_only':True,
        'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,
        'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,
        'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'INTEGRATE_SITE_USE_EVIDENCE_INTO_FIND_PROPERTY_PROFILES_AND_SELECT_NEXT_TARGETED_CONSTRAINT_LAYER_BY_INFORMATION_VALUE; DO_NOT_INFER_ENTITLEMENT'
    }

if __name__=='__main__':
    print(json.dumps(build_find6(),indent=2,sort_keys=True))
