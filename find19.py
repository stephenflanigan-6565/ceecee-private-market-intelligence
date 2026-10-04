#!/usr/bin/env python3
import os,re,json,math,statistics
from collections import defaultdict,Counter
from datetime import datetime,timezone

VERSION='FIND19'; MARKET='WESTHAMPTON_BEACH_NY'
FAMS=('PROPERTY_CONTEXT','ASSESSMENT_CONTEXT')
MIN_LOCAL_PEERS=8
LARGE_PCT=.90
MIN_MEDIAN_MULTIPLE=1.50

ALIASES={
'address':['property_address','parcel_address','address','fulladdress','full_address','site_address','situs_address'],
'property_class':['property_class','class','propertyclass','landuse','land_use','use_class','property_type'],
'acres':['acres','acreage','lot_acres','parcel_acres'],
'assessment_total':['assessment_total','total_assessment','assessed_total','total_assessed_value','assessed_value'],
'land_assessment':['land_assessment','assessed_land','land_assessed_value'],
'living_sqft':['living_sqft','living_area','sqft','square_feet']}
SUFFIX={'ROAD':'RD','AVENUE':'AVE','STREET':'ST','LANE':'LN','DRIVE':'DR','COURT':'CT','HIGHWAY':'HWY','BOULEVARD':'BLVD','PLACE':'PL','TERRACE':'TER'}

def _payload(v):
    if isinstance(v,dict): return v
    try:
        x=json.loads(v) if v else {}; return x if isinstance(x,dict) else {}
    except Exception:return {}
def _flat(d):
    out={}
    def walk(x):
        if not isinstance(x,dict):return
        for k,v in x.items():
            key=str(k).lower().strip()
            if isinstance(v,dict):walk(v)
            elif key not in out and v not in (None,''):out[key]=v
    walk(d);return out
def _pick(f,aa):
    for a in aa:
        if f.get(a) not in (None,''):return f[a]
    return None
def _num(v):
    try:
        if v is None or isinstance(v,bool):return None
        x=float(str(v).replace(',','').replace('$','').strip());return x if math.isfinite(x) else None
    except Exception:return None
def _pct(xs,x):
    if x is None or not xs:return None
    s=sorted(xs);return (sum(v<x for v in s)+.5*sum(v==x for v in s))/len(s)
def _street(addr):
    if not addr:return None
    s=re.sub(r'[^A-Z0-9 ]+',' ',str(addr).upper()).strip(); parts=s.split()
    if parts and re.match(r'^\d+[A-Z]?$',parts[0]):parts=parts[1:]
    if parts and parts[-1] in SUFFIX:parts[-1]=SUFFIX[parts[-1]]
    return ' '.join(parts) or None

def build_find19():
    import psycopg
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    try:
        cur=conn.cursor();cur.execute('''SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
          WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
          ORDER BY parcel_id,evidence_family,evidence_key''',(MARKET,list(FAMS))); rows=cur.fetchall()
    finally:conn.close()
    by=defaultdict(dict)
    for pid,fam,pj in rows:
        for k,v in _flat(_payload(pj)).items():
            if k not in by[str(pid)] and v not in (None,''):by[str(pid)][k]=v
    props=[]; coverage=Counter()
    for pid,m in by.items():
        addr=_pick(m,ALIASES['address']); pc=_pick(m,ALIASES['property_class']); ac=_num(_pick(m,ALIASES['acres']))
        total=_num(_pick(m,ALIASES['assessment_total'])); land=_num(_pick(m,ALIASES['land_assessment'])); sqft=_num(_pick(m,ALIASES['living_sqft']))
        if addr is not None:coverage['address']+=1
        if pc is not None:coverage['property_class']+=1
        if ac is not None and ac>0:coverage['acres']+=1
        if total is not None:coverage['assessment_total']+=1
        if land is not None:coverage['land_assessment']+=1
        st=_street(addr)
        if not st or not pc or ac is None or ac<=0:continue
        imp=total-land if total is not None and land is not None and total>=land else None
        land_share=land/total if total not in (None,0) and land is not None else None
        props.append({'parcel_id':str(pid),'property_address':str(addr).strip(),'property_class':str(pc).strip(),
          'street_context':st,'acres':ac,'assessment_total':total,'land_assessment':land,'improvement_assessment':imp,
          'land_share':land_share,'living_sqft':sqft})
    groups=defaultdict(list)
    for p in props:groups[(p['street_context'],p['property_class'])].append(p)
    cand=[]; excluded=Counter()
    for p in props:
        peers=[x for x in groups[(p['street_context'],p['property_class'])] if x['parcel_id']!=p['parcel_id']]
        if len(peers)<MIN_LOCAL_PEERS:excluded['SAME_STREET_SAME_CLASS_PEERS_LT_8']+=1;continue
        acres=[x['acres'] for x in peers if x['acres'] is not None]
        if len(acres)<MIN_LOCAL_PEERS:excluded['VALID_ACREAGE_PEERS_LT_8']+=1;continue
        med=statistics.median(acres); ap=_pct(acres,p['acres'])
        if ap is None or ap<LARGE_PCT or med<=0 or p['acres']<med*MIN_MEDIAN_MULTIPLE:continue
        # Second independent relationship: the parcel is not merely large; current improvement/economic use is light relative to its land position.
        corroboration=[]
        if p['improvement_assessment'] is not None and p['improvement_assessment']<=0:corroboration.append('ZERO_ASSESSED_IMPROVEMENT_COMPONENT')
        if p['land_share'] is not None and p['land_share']>=.80:corroboration.append('LAND_HEAVY_ASSESSMENT_RELATIONSHIP')
        sqft_peers=[x['living_sqft'] for x in peers if x['living_sqft'] is not None and x['living_sqft']>0]
        sqft_pct=_pct(sqft_peers,p['living_sqft']) if p['living_sqft'] is not None and p['living_sqft']>0 and sqft_peers else None
        if sqft_pct is not None and sqft_pct<=.25:corroboration.append('SMALL_IMPROVEMENT_RELATIVE_TO_LOCAL_COMPATIBLE_CONTEXT')
        if not corroboration:continue
        cand.append({'parcel_id':p['parcel_id'],'property_address':p['property_address'],'property_class':p['property_class'],
          'opportunity_family':'OU_007_LOT_LINE_RECONFIGURATION_OPPORTUNITY','state':'RECONFIGURATION_QUESTION_SUPPORTED_NOT_PROVEN',
          'observed_relationship':'PARCEL_MATERIALLY_LARGER_THAN_SAME_STREET_SAME_CLASS_CONTEXT_WITH_LIGHTER_LAND_USE_SIGNAL',
          'local_context':{'street_context':p['street_context'],'same_street_same_class_peer_count':len(peers),
            'subject_acres':round(p['acres'],6),'peer_median_acres':round(med,6),'subject_acreage_percentile':round(ap,6),
            'subject_to_peer_median_acreage_multiple':round(p['acres']/med,6),
            'subject_living_sqft_percentile':round(sqft_pct,6) if sqft_pct is not None else None},
          'corroboration':corroboration,
          'hypothesis':'PARCEL_STRUCTURE_MAY_SUPPORT_A_LOT_LINE_OR_RECONFIGURATION_QUESTION_WORTH_PRESERVING',
          'contradictions_and_unknowns':['TRUE_PARCEL_GEOMETRY_NOT_TESTED','FRONTAGE_NOT_TESTED','ACCESS_NOT_TESTED','LEGAL_LOT_CONFIGURATION_NOT_TESTED','ZONING_DIMENSIONAL_COMPLIANCE_NOT_TESTED'],
          'decision_effect':'PRESERVE_RECONFIGURATION_HYPOTHESIS_ONLY; DO_NOT_CALL_SUBDIVIDABLE_OR_BUILDABLE',
          'next_best_question':'Only if this property survives independent novelty/corroboration review: what single geometry, frontage, access, or legal-lot fact would most strongly destroy or support the reconfiguration hypothesis?',
          'seller_intent':'UNKNOWN','contact_authorized':False,
          'limits':['STREET_CONTEXT_IS_NOT_TRUE_ADJACENCY','ACREAGE_OUTLIER_IS_NOT_SUBDIVISION_PROOF','RECONFIGURATION_IS_NOT_ENTITLEMENT','NO_SELLER_INTENT_INFERENCE']})
    cand.sort(key=lambda r:(-r['local_context']['subject_to_peer_median_acreage_multiple'],-len(r['corroboration']),r['parcel_id']))
    return {'status':'ok','version':VERSION,'mode':'READ_ONLY_WHOLE_MARKET_PARCEL_RECONFIGURATION_DISCOVERY_EXPERIMENT',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'TEST_OU_007_LOT_LINE_RECONFIGURATION_AS_A_GENUINELY_INDEPENDENT_PROPERTY_DISCOVERY_FAMILY_USING_EXISTING_WHB_EVIDENCE_ONLY',
      'architecture':{'whole_market_test':True,'opportunity_family':'OU_007_LOT_LINE_RECONFIGURATION_OPPORTUNITY','independent_of_improvement_age':True,'independent_of_redevelopment_halo':True,'legal_geometry_required_for_proof':True,'discovery_not_entitlement':True},
      'summary':{'working_property_universe':len(by),'valid_address_class_acreage_records':len(props),'same_street_same_class_contexts':len(groups),'observed_reconfiguration_hypotheses':len(cand),'exclusions':dict(excluded)},
      'field_coverage':dict(coverage),
      'research_thresholds':{'status':'EXPERIMENTAL_OBSERVABILITY_ONLY_NOT_UNIVERSAL_RULES','minimum_same_street_same_class_peers':MIN_LOCAL_PEERS,'subject_acreage_percentile_at_or_above':LARGE_PCT,'minimum_subject_to_peer_median_acreage_multiple':MIN_MEDIAN_MULTIPLE,'second_relationship_required':True},
      'candidates':cand[:60],'candidate_payload':{'total':len(cand),'returned':min(60,len(cand)),'complete':len(cand)<=60,'display_policy':'DIAGNOSTIC_EXTREMENESS_NOT_OPERATOR_RANKING'},
      'interpretation_policy':{'data_serves_decision':True,'large_parcel_alone_not_opportunity':True,'street_context_not_true_adjacency':True,'lot_line_reconfiguration_not_subdivision':True,'zoning_not_entitlement':True,'unknown_valid_state':True,'no_generic_enrichment':True,'route_kill_never_equals_property_kill':True,'seller_intent_remains_unknown':True},
      'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
      'next_if_verified':'COMPARE FIND19 PARCELS AGAINST THE EXISTING 230-PROPERTY DISCOVERY UNIVERSE. PROMOTE OU_007 ONLY IF IT ADDS MEANINGFUL NOVEL DISCOVERY OR DISTINCT CORROBORATION; OTHERWISE KILL THE RAIL. DO NOT FETCH GEOMETRY OR FRONTAGE UNTIL A SURVIVING PROPERTY MAKES THAT FACT MATERIAL.'}

if __name__=='__main__':print(json.dumps(build_find19(),indent=2,sort_keys=True))
