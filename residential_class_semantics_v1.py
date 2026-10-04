from datetime import datetime, timezone
from collections import Counter
from assessment_route_contextual_peer_scale_v1 import build_assessment_route_contextual_peer_scale_v1

VERSION='RESIDENTIAL_CLASS_SEMANTICS_V1'
OFFICIAL_SOURCE='New York State Department of Taxation and Finance / ORPTS Property Type Classification Codes'
OFFICIAL_URL='https://www.tax.ny.gov/research/property/assess/manuals/prclas.htm'
SEMANTICS={
 '210':{
   'meaning':'ONE_FAMILY_YEAR_ROUND_RESIDENCE',
   'definition':'One family dwelling constructed for year-round occupancy.',
   'reasoning_use':'VALID_RESIDENTIAL_PEER_CLASS; DOES_NOT_PROVE OWNERSHIP FORM OR SELLER INTENT'
 },
 '260':{
   'meaning':'SEASONAL_RESIDENCE',
   'definition':'Dwelling unit generally used for seasonal occupancy; not constructed for year-round occupancy.',
   'reasoning_use':'VALID_SEASONAL_RESIDENTIAL_PEER_CLASS; DOES_NOT PROVE OWNERSHIP FORM OR SELLER INTENT'
 },
 '281':{
   'meaning':'MULTIPLE_RESIDENCES',
   'definition':'More than one residential dwelling on one parcel; may be a mixture of residential dwelling types.',
   'reasoning_use':'DO_NOT TREAT AS ORDINARY SINGLE-DWELLING PHYSICAL PEER WITHOUT MULTI-RESIDENCE CHARACTERISTICS'
 }
}

def build_residential_class_semantics_v1():
    prior=build_assessment_route_contextual_peer_scale_v1()
    if prior.get('status')!='ok':
        raise RuntimeError('scaled contextual peer checkpoint unavailable')
    cases=[]
    for c in prior.get('cases',[]):
        pc=str(c.get('property_class') or '')
        out=dict(c)
        sem=SEMANTICS.get(pc)
        out['resolved_class_semantics']=sem or {'meaning':'UNRESOLVED_SOURCE_CLASSIFICATION','reasoning_use':'DO_NOT ASSERT CLASS MEANING'}
        if c.get('state')=='WEAKENS_UNDER_CONTEXTUAL_PEERS':
            out['post_semantic_route']='HOLD_WEAKENED_NO_EXTERNAL_LOOKUP'
            out['external_lookup_authorized']=False
        elif pc=='281':
            out['post_semantic_route']='RESOLVE_MULTI_RESIDENCE_PROPERTY_CHARACTERISTICS_BEFORE_EXTERNAL_ASSESSMENT_CAUSE_LOOKUP'
            out['external_lookup_authorized']=False
            out['peer_interpretation']='PRIOR SAME_CLASS FALLBACK IS DIAGNOSTIC ONLY; MULTIPLE-DWELLING COUNT/CONFIGURATION MAY MATERIALLY EXPLAIN ASSESSMENT ALLOCATION'
        elif pc=='210' and c.get('survives_kill_test') is True:
            out['post_semantic_route']='ELIGIBLE_FOR_TARGETED_AUTHORITATIVE_PROPERTY_FACT_LOOKUP'
            out['external_lookup_authorized']=True
            out['peer_interpretation']='ONE_FAMILY_YEAR_ROUND CLASS IS SEMANTICALLY COMPATIBLE WITH RESIDENTIAL PHYSICAL PEER TEST'
        elif pc=='260' and c.get('survives_kill_test') is True:
            out['post_semantic_route']='PROVEN_SINGLE_CASE_CONTINUE_PROPERTY_CAUSE_RESEARCH'
            out['external_lookup_authorized']=True
            out['peer_interpretation']='SEASONAL RESIDENCE SEMANTICS ALREADY PROVEN WITH DUNE/PHYSICAL CONTEXT'
        else:
            out['post_semantic_route']='KEEP_UNRESOLVED'
            out['external_lookup_authorized']=False
        out['seller_intent']='UNKNOWN'; out['contact_authorized']=False
        cases.append(out)
    routes=Counter(c['post_semantic_route'] for c in cases)
    classes=Counter(str(c.get('property_class') or '') for c in cases)
    survivors=[c for c in cases if c.get('survives_kill_test') is True]
    eligible=[c for c in cases if c.get('external_lookup_authorized')]
    return {
      'status':'ok','version':VERSION,'mode':'READ_ONLY_AUTHORITATIVE_CLASS_SEMANTICS_GATE',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'source_checkpoint':{'version':prior.get('version'),'cases_tested':len(cases),'survivors':len(survivors)},
      'authoritative_semantics_source':{'authority':OFFICIAL_SOURCE,'url':OFFICIAL_URL,'external_calls_this_endpoint':0},
      'resolved_semantics':SEMANTICS,
      'class_distribution':dict(classes),
      'summary':{'cases_received':len(cases),'survivors_received':len(survivors),'post_semantic_routes':dict(routes),'targeted_external_lookup_eligible':len(eligible),'bulk_external_lookup_authorized':False},
      'cases':cases,
      'decision':{
        'class_210':'SEMANTICALLY_RESOLVED_ONE_FAMILY_YEAR_ROUND; SURVIVORS MAY ENTER CONTROLLED TARGETED FACT LOOKUP',
        'class_281':'SEMANTICALLY_RESOLVED_MULTIPLE_RESIDENCES; DO NOT TREAT AS ORDINARY SINGLE-DWELLING PEERS; RESOLVE MULTI-RESIDENCE CHARACTERISTICS FIRST',
        'class_260':'SEASONAL_RESIDENCE SEMANTIC REMAINS LOCKED',
        'weakened_case':'REMAINS HELD; DO NOT SPEND EXTERNAL LOOKUP YET',
        'seller_intent':'UNKNOWN','contact_authorized':False
      },
      'policy':{'class_semantics_before_interpretation':True,'multiple_residences_require_multi_structure_context':True,'one_family_year_round_may_use_residential_physical_peers':True,'property_class_does_not_prove_ownership_form':True,'missing_information_nonblocking':True,'seller_intent_inferred':False,'marketing_execution':False},
      'database_writes':0,
      'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'HOLD_CLASS_281_FOR_MULTI_RESIDENCE_CONTEXT; THEN RUN_ONE_CONTROLLED_CLASS_210_AUTHORITATIVE_PROPERTY_FACT_LOOKUP_TO_TEST_CAUSAL_RESOLUTION_BEFORE_SCALING_EXTERNAL_RESEARCH'
    }
