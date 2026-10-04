#!/usr/bin/env python3
import json
from collections import Counter
from datetime import datetime,timezone
from find10 import build_find10
from find16 import build_find16

VERSION='FIND17'
# NYS ORPTS statewide base property-class semantics. Local suffixes may add ownership/waterfront
# context, so classification uses only the leading three-digit base code.
ORPTS_BASE={
 '210':('ONE_FAMILY_YEAR_ROUND_RESIDENCE','RESIDENTIAL_IMPROVED'),
 '311':('RESIDENTIAL_VACANT_LAND','VACANT_OR_MINIMALLY_IMPROVED'),
 '312':('RESIDENTIAL_LAND_WITH_SMALL_NON_LIVING_IMPROVEMENT','VACANT_OR_MINIMALLY_IMPROVED'),
 '314':('RURAL_VACANT_LOT_10_ACRES_OR_LESS','VACANT_OR_MINIMALLY_IMPROVED'),
 '315':('UNDERWATER_VACANT_LAND','VACANT_OR_MINIMALLY_IMPROVED'),
 '322':('RESIDENTIAL_VACANT_LAND_OVER_10_ACRES','VACANT_OR_MINIMALLY_IMPROVED'),
}

def _base_code(v):
    s=str(v or '').strip().upper()
    return s[:3] if len(s)>=3 and s[:3].isdigit() else None

def build_find17():
    f10=build_find10()
    f16=build_find16()
    existing230=set()
    # FIND16 source universe was 226; its novel candidates are the four additions.
    # We preserve that checkpoint without allowing FIND17 property-form evidence to manufacture seller qualification.
    try:
        from find15 import _expanded_discovered_universe
        _,_,existing226,_=_expanded_discovered_universe(); existing230.update(existing226)
    except Exception:
        pass
    for x in (f16.get('candidates') or []):
        if x.get('novel_to_existing_226_property_universe'): existing230.add(str(x.get('parcel_id')))

    results=[]; states=Counter(); novel=0
    for r in (f10.get('results') or []):
        fact=r.get('authoritative_town_parcel_form_fact') or {}
        raw=fact.get('PROP_TYPE'); base=_base_code(raw)
        desc,family=ORPTS_BASE.get(base,('UNRESOLVED_ORPTS_BASE_PROPERTY_FORM','UNKNOWN'))
        pid=str(r.get('parcel_id'))
        rec={
          'parcel_id':pid,'property_address':r.get('property_address'),'observed_prop_type':raw,
          'orpts_base_code':base,'orpts_interpretation':desc,
          'source_evidence_state':r.get('evidence_state'),'seller_intent':'UNKNOWN','contact_authorized':False,
          'existing_230_property_universe_coverage':pid in existing230,
          'why_this_case_was_tested':'PRIOR_ZERO_OR_CONFLICTING_IMPROVEMENT_EVIDENCE_REQUIRED_PROPERTY_FORM_RESOLUTION',
          'limits':['PROPERTY_CLASS_DESCRIBES_ASSESSMENT_USE_FORM_NOT_BUILDABILITY','PROPERTY_CLASS_DOES_NOT_PROVE_CURRENT_PHYSICAL_CONDITION','PROPERTY_CLASS_DOES_NOT_PROVE_ENTITLEMENT','PROPERTY_CLASS_DOES_NOT_PROVE_SELLER_INTENT']}
        if family=='VACANT_OR_MINIMALLY_IMPROVED':
            rec.update({'state':'SUPPORTED_PROPERTY_FORM_HYPOTHESIS','property_form_family':'VACANT_OR_MINIMALLY_IMPROVED',
              'hypothesis':'OU_004_VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM_SUPPORTED',
              'decision_effect':'PROPERTY_FORM_NOW_SUPPORTS_A_REAL_LAND_OR_INFILL_RESEARCH_HYPOTHESIS_BUT_NOT_BUILDABILITY',
              'next_question':'What single lawful-use, access, dimensional, or site-constraint fact could most strongly destroy or support an infill/site opportunity on this parcel?',
              'novel_to_existing_230_property_universe':pid not in existing230})
            if pid not in existing230: novel+=1
        elif family=='RESIDENTIAL_IMPROVED':
            rec.update({'state':'VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM','property_form_family':'RESIDENTIAL_IMPROVED',
              'hypothesis':'OU_004_NOT_SUPPORTED_BY_CURRENT_PROPERTY_FORM',
              'decision_effect':'DO_NOT_TREAT_ZERO_OR_MISSING_IMPROVEMENT_FIELDS_AS_VACANT; PRESERVE_OTHER_INDEPENDENT_PROPERTY_ROUTES',
              'next_question':'No vacancy research required from this route. Continue only through another independent property hypothesis.',
              'novel_to_existing_230_property_universe':False})
        else:
            rec.update({'state':'UNKNOWN_NONBLOCKING','property_form_family':'UNKNOWN','hypothesis':'OU_004_UNRESOLVED',
              'decision_effect':'DO_NOT_INFER_VACANCY; NO_FOLLOW_ON_DATA_HUNT_UNLESS_PROPERTY_SURVIVES_FOR_ANOTHER_REASON',
              'next_question':'None unless property-form resolution later becomes material to a surviving independent opportunity thesis.',
              'novel_to_existing_230_property_universe':False})
        states[rec['state']]+=1;results.append(rec)
    supported=[x for x in results if x['state']=='SUPPORTED_PROPERTY_FORM_HYPOTHESIS']
    contradicted=[x for x in results if x['state']=='VACANCY_HYPOTHESIS_CONTRADICTED_BY_PROPERTY_FORM']
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_VACANT_MINIMALLY_IMPROVED_PROPERTY_FORM_LEARNING_EXPERIMENT',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_OU_004_VACANT_OR_MINIMALLY_IMPROVED_PROPERTY_FORM_AND_OPEN_OU_005_INFILL_ONLY_WHERE_EXISTING_TARGETED_EVIDENCE_SUPPORTS_IT',
      'source_checkpoint':'FIND10_TARGETED_PROPERTY_FORM_FACTS_PLUS_FIND16_PROMOTED_230_PROPERTY_DISCOVERY_UNIVERSE',
      'architecture':{'existing_discovery_universe_properties':len(existing230),'generic_market_property_form_enrichment':False,
        'targeted_cases_only':True,'learns_from_prior_zero_improvement_false_inference':True,
        'statewide_base_code_semantics':'NYS_ORPTS','local_suffix_not_used_to_infer_vacancy':True},
      'summary':{'targeted_property_form_cases':len(results),'supported_vacant_or_minimally_improved':len(supported),
        'vacancy_hypothesis_contradicted_by_residential_property_form':len(contradicted),'unknown_nonblocking':states['UNKNOWN_NONBLOCKING'],
        'novel_to_existing_230_property_universe':novel,'states':dict(states)},
      'results':results,
      'supported_property_form_hypotheses':supported,
      'interpretation_policy':{'data_serves_decision':True,'zero_improvement_not_vacancy':True,'missing_living_area_not_vacancy':True,
        'orpts_300_series_can_support_vacant_or_minimally_improved_property_form':True,'orpts_210_base_contradicts_vacant_land_inference':True,
        'property_form_not_buildability':True,'property_form_not_seller_intent':True,'no_generic_enrichment':True,
        'unknown_valid_state':True,'route_kill_never_equals_property_kill':True,'human_verification_only_if_later_material':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,
        'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,
        'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'PROMOTE ONLY THE SUPPORTED VACANT_OR_MINIMALLY_IMPROVED PROPERTY_FORM RELATIONSHIP. THEN TEST WHETHER EXISTING SITE/ZONING CONTEXT CAN SUPPORT OR KILL AN OU_005_INFILL HYPOTHESIS WITHOUT GENERIC ENRICHMENT.'}

if __name__=='__main__': print(json.dumps(build_find17(),indent=2,sort_keys=True))
