#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from find9 import build_find9

VERSION='FIND10'
PARCEL_URL='https://gis.southamptontownny.gov/gisserver/rest/services/DataServices/TaxParcels/MapServer/0/query'

# One isolated information-value test only. No generic enrichment.
REQUEST_FIELDS='OBJECTID,DSBL,PARCEL_ID,CIVIC,ST_ADDRS,SCTM,PROP_TYPE'

def _get(url, params, timeout=12):
    q=urllib.parse.urlencode(params)
    req=urllib.request.Request(url+'?'+q, headers={'User-Agent':'PMI-Research/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def _parcel_form_fact(parcel_id, address=None):
    raw=''.join(ch for ch in str(parcel_id or '') if ch.isdigit())
    diag={'query_field':'SCTM','query_form':raw,'address_cross_check_only':address}
    if len(raw)!=19:
        return None,'INVALID_PMI_SCTM_FORM',diag
    safe=raw.replace("'","''")
    data=_get(PARCEL_URL, {
        'f':'json','where':f"SCTM='{safe}'",'outFields':REQUEST_FIELDS,
        'returnGeometry':'false'
    })
    if data.get('error'):
        diag['service_error']=data.get('error')
        return None,'SOURCE_QUERY_REJECTED',diag
    fs=data.get('features') or []
    diag['match_count']=len(fs)
    if len(fs)!=1:
        return None,('NO_SCTM_MATCH' if not fs else 'MULTIPLE_SCTM_MATCHES'),diag
    a=fs[0].get('attributes') or {}
    diag['returned_sctm']=a.get('SCTM')
    diag['returned_st_addrs']=a.get('ST_ADDRS')
    diag['address_exact_cross_check']=(str(a.get('ST_ADDRS') or '').strip().upper()==str(address or '').strip().upper())
    fact={k:a.get(k) for k in ('DSBL','SCTM','ST_ADDRS','PARCEL_ID','PROP_TYPE')}
    return fact,None,diag

def build_find10():
    f9=build_find9(include_all_profiles=True)
    targets=[p for p in (f9.get('profiles') or []) if p.get('current_find_state')=='TARGETED_FACT_REQUIRED']
    results=[]; outcomes=Counter(); prop_types=Counter()
    for p in targets:
        lr=p.get('land_route') or {}
        rec={
          'parcel_id':p.get('parcel_id'),'property_address':p.get('property_address'),
          'find9_state':p.get('current_find_state'),'causal_family':lr.get('causal_family'),
          'question_being_tested':p.get('next_best_property_question'),
          'why_pmi_noticed_it':p.get('why_pmi_noticed_it'),
          'seller_intent':'UNKNOWN','contact_authorized':False}
        try:
            fact,err,diag=_parcel_form_fact(p.get('parcel_id'),p.get('property_address'))
            rec['identity_diagnostic']=diag
            if err:
                rec['evidence_state']='UNKNOWN_NONBLOCKING_SOURCE_FAILURE'
                rec['adapter_state']=err; outcomes[err]+=1
                rec['decision_effect']='DO_NOT_HOLD_ENGINE; RETAIN_TARGETED_FACT_OR_HUMAN_VERIFICATION_IF_PROPERTY_SURVIVES'
            else:
                rec['authoritative_town_parcel_form_fact']=fact
                pt=fact.get('PROP_TYPE')
                if pt is None or str(pt).strip()=='':
                    rec['evidence_state']='AUTHORITATIVE_SOURCE_PRESENT_FORM_FIELD_EMPTY'
                    outcomes[rec['evidence_state']]+=1
                    rec['decision_effect']='SOURCE_DOES_NOT_RESOLVE_CURRENT_PROPERTY_FORM; NO_FURTHER_DATA_HUNT'
                else:
                    rec['evidence_state']='AUTHORITATIVE_PROPERTY_TYPE_FACT_PRESENT'
                    outcomes[rec['evidence_state']]+=1; prop_types[str(pt)]+=1
                    rec['decision_effect']='USE_AS_ONE_PROPERTY_FORM_FACT_ONLY; DO_NOT_INFER_VACANCY_BUILDABILITY_ENTITLEMENT_OR_SELLER_INTENT'
        except Exception as e:
            rec['evidence_state']='UNKNOWN_NONBLOCKING_SOURCE_FAILURE'
            rec['adapter_state']='SOURCE_REQUEST_ERROR'; rec['error_type']=type(e).__name__; rec['error']=str(e)[:300]
            outcomes['SOURCE_REQUEST_ERROR']+=1
            rec['decision_effect']='DO_NOT_HOLD_ENGINE; RETAIN_TARGETED_FACT_OR_HUMAN_VERIFICATION_IF_PROPERTY_SURVIVES'
        results.append(rec)
    return {
      'status':'ok','version':VERSION,
      'mode':'READ_ONLY_TARGETED_AUTHORITATIVE_PROPERTY_FORM_FACT_TEST',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_ONE_ALREADY_AVAILABLE_AUTHORITATIVE_TOWN_PROPERTY_FORM_FACT_ONLY_FOR_EXISTING_FIND9_TARGETED_FACT_REQUIRED_CASES',
      'source_checkpoint':'FIND9_PROMOTED_PROPERTY_INTELLIGENCE_CHASSIS',
      'source_contract':{
        'source':'Town of Southampton DataServices/TaxParcels MapServer layer 0',
        'identity':'EXACT_SCTM_19_DIGIT_IDENTITY',
        'field_tested':'PROP_TYPE',
        'scope':'ONLY_EXISTING_FIND9_TARGETED_FACT_REQUIRED_CASES',
        'new_dataset_added':False,
        'generic_enrichment':False},
      'summary':{
        'find9_profiles':len(f9.get('profiles') or []),
        'targeted_fact_required_cases':len(targets),
        'results':len(results),
        'adapter_outcomes':dict(outcomes),
        'property_types_observed':dict(prop_types),
        'data_hunt_policy':'IF_PROP_TYPE_DOES_NOT_MATERIALLY_RESOLVE_THE_EXISTING_QUESTION_STOP_AND_ROUTE_TO_HUMAN_VERIFICATION_OR_CONTINUE_NONBLOCKING'},
      'results':results,
      'interpretation_policy':{
        'data_serves_decision':True,
        'one_fact_test_only':True,
        'property_type_not_vacancy_proof':True,
        'property_type_not_buildability':True,
        'property_type_not_entitlement':True,
        'property_type_not_seller_intent':True,
        'missing_fact_nonblocking_unless_material_to_specific_hypothesis':True,
        'no_follow_on_data_hunt_from_missing_or_ambiguous_prop_type':True,
        'route_kill_never_equals_property_kill':True,
        'why_found_history_preserved':True},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,
        'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,
        'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'INTERPRET WHETHER PROP_TYPE MATERIALLY RESOLVES EACH EXISTING TARGETED CASE. RESOLVE ONLY WHAT THE FACT SUPPORTS. OTHERWISE MARK HUMAN_VERIFICATION_IF_NEEDED_AND_RETURN TO NEW_OPPORTUNITY_DISCOVERY; DO_NOT START_ANOTHER_PROPERTY_FORM_DATA_HUNT.'
    }

if __name__=='__main__':
    print(json.dumps(build_find10(),indent=2,sort_keys=True))
