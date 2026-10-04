#!/usr/bin/env python3
import os,json,math,statistics
from collections import defaultdict,Counter
from datetime import datetime,timezone
VERSION='FIND2'; MARKET='WESTHAMPTON_BEACH_NY'; FAMS=('PROPERTY_CONTEXT','ASSESSMENT_CONTEXT')
ALIASES={
'address':['property_address','parcel_address','address','fulladdress','full_address','site_address','situs_address'],
'property_class':['property_class','class','propertyclass','landuse','land_use','use_class','property_type'],
'acres':['acres','acreage','lot_acres','parcel_acres'],
'assessment_total':['assessment_total','total_assessment','assessed_total','total_assessed_value','assessed_value'],
'land_assessment':['land_assessment','assessed_land','land_assessed_value'],
'year_built':['year_built','yearbuilt'],'living_sqft':['living_sqft','living_area','sqft','square_feet']}
NUM={'acres','assessment_total','land_assessment','year_built','living_sqft'}
def _payload(v):
 if isinstance(v,dict): return v
 try:
  x=json.loads(v) if v else {}; return x if isinstance(x,dict) else {}
 except:return {}
def _flat(d):
 out={}
 def walk(x):
  if not isinstance(x,dict):return
  for k,v in x.items():
   key=str(k).lower().strip()
   if isinstance(v,dict): walk(v)
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
 except:return None
def _pct(xs,x):
 if x is None or not xs:return None
 s=sorted(xs);return (sum(v<x for v in s)+.5*sum(v==x for v in s))/len(s)
def _med(xs):return statistics.median(xs) if xs else None
def build_find2():
 import psycopg
 conn=psycopg.connect(os.environ['DATABASE_URL'])
 try:
  cur=conn.cursor();cur.execute('''SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
   WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
   ORDER BY parcel_id,evidence_family,evidence_key''',(MARKET,list(FAMS)));rows=cur.fetchall()
 finally:conn.close()
 by=defaultdict(dict)
 for pid,fam,pj in rows:
  by[pid].setdefault(fam,{})
  for k,v in _flat(_payload(pj)).items():
   if k not in by[pid][fam] and v not in (None,''):by[pid][fam][k]=v
 recs=[];coverage=Counter()
 for pid,fams in by.items():
  merged={}
  for fam in FAMS:merged.update(fams.get(fam,{}))
  r={'parcel_id':pid}
  for k,aa in ALIASES.items():
   v=_pick(merged,aa);r[k]=_num(v) if k in NUM else (str(v).strip() if v not in (None,'') else None)
   if r[k] is not None:coverage[k]+=1
  if r['acres'] is not None and r['acres']<=0:r['acres']=None
  t,l=r['assessment_total'],r['land_assessment']
  r['improvement_assessment']=t-l if t is not None and l is not None and t>=l else None
  r['improvement_to_land']=r['improvement_assessment']/l if l not in (None,0) and r['improvement_assessment'] is not None else None
  r['land_share']=l/t if t not in (None,0) and l is not None else None
  recs.append(r)
 groups=defaultdict(list)
 for r in recs:
  if r['property_class']:groups[r['property_class']].append(r)
 candidates=[];family_counts=Counter();excluded=Counter()
 for r in recs:
  peers=groups.get(r['property_class'],[])
  if len(peers)<20: excluded['CLASS_PEER_GROUP_LT_20']+=1;continue
  ratio=[p['improvement_to_land'] for p in peers if p['improvement_to_land'] is not None]
  share=[p['land_share'] for p in peers if p['land_share'] is not None]
  acres=[p['acres'] for p in peers if p['acres'] is not None]
  sqft=[p['living_sqft'] for p in peers if p['living_sqft'] is not None]
  if r['improvement_to_land'] is None or r['land_share'] is None: excluded['MISSING_LAND_IMPROVEMENT_COMPONENTS']+=1;continue
  rp=_pct(ratio,r['improvement_to_land']); sp=_pct(share,r['land_share']); ap=_pct(acres,r['acres']); qp=_pct(sqft,r['living_sqft'])
  # Relative gates only: no universal dollar, acreage, or luxury threshold.
  routes=[]
  if rp is not None and sp is not None and rp<=.10 and sp>=.90:
   routes.append('LAND_DOMINANT_UNDER_IMPROVEMENT')
  if routes and ap is not None and ap>=.75:
   routes.append('EXCESS_OR_OVERSIZED_LAND_CONTEXT')
  if routes and qp is not None and qp<=.25:
   routes.append('SMALL_IMPROVEMENT_RELATIVE_TO_CLASS')
  if not routes:continue
  # Strength requires the core land-dominant relationship; extra routes are corroboration, not scoring.
  family_counts.update(routes)
  candidates.append({
   'parcel_id':r['parcel_id'],'property_address':r['address'],'property_class':r['property_class'],
   'observed_relationships':routes,
   'actual_values':{'acres':r['acres'],'living_sqft':r['living_sqft'],'year_built':r['year_built'],'land_assessment':r['land_assessment'],'improvement_assessment':r['improvement_assessment'],'assessment_total':r['assessment_total'],'improvement_to_land_ratio':round(r['improvement_to_land'],6),'land_share_of_assessment':round(r['land_share'],6)},
   'peer_context':{'same_class_peer_count':len(peers),'improvement_to_land_peer_median':round(_med(ratio),6) if ratio else None,'improvement_to_land_percentile':round(rp,6) if rp is not None else None,'land_share_percentile':round(sp,6) if sp is not None else None,'acreage_percentile':round(ap,6) if ap is not None else None,'living_sqft_percentile':round(qp,6) if qp is not None else None},
   'hypothesis':'PROPERTY_OR_LAND_MAY_BE_UNDER_IMPROVED_RELATIVE_TO_CURRENT_LAND_POSITION_AND_COMPATIBLE_PEERS',
   'state':'RESEARCH_ACTIVE','seller_intent':'UNKNOWN','contact_authorized':False,
   'kill_tests':['VERIFY_PROPERTY_FORM_AND_USE','VERIFY_SITE_CONSTRAINTS_OR_NONSTANDARD_PARCEL_FUNCTION','VERIFY_CURRENT_IMPROVEMENT_FACTS','CHECK_IF_RECENT_REDEVELOPMENT_ALREADY_EXPLAINS_RELATIONSHIP','CHECK_LOCAL_MICRO_MARKET_CONTEXT_BEFORE_ECONOMIC_CONCLUSION'],
   'next_question':'What single authoritative site/use/improvement fact would most strengthen or destroy the under-improvement or land-utilization hypothesis?',
   'find1_integration':{'route':'LAND_PROPERTY_UTILIZATION','state':'ACTIVE_RESEARCH_ROUTE','independent_of_closed_class_210_assessment_route':True}
  })
 # diagnostic ordering only: multiple corroborating relationships first, then extremeness of core relative relationship
 candidates.sort(key=lambda x:(-len(x['observed_relationships']),x['peer_context']['improvement_to_land_percentile'],x['parcel_id']))
 return {'status':'ok','version':VERSION,'mode':'READ_ONLY_LAND_PROPERTY_UTILIZATION_DISCOVERY','generated_at':datetime.now(timezone.utc).isoformat(),
  'architecture':{'integrates_with':'FIND1','independent_discovery_route':'LAND_PROPERTY_UTILIZATION','property_not_seller_model':True,'contextual_not_universal_thresholds':True,'assessment_components_used_as_supporting_economic_evidence_not_seller_signal':True},
  'summary':{'whole_market_properties':len(recs),'candidate_properties':len(candidates),'candidate_relationship_counts':dict(family_counts),'data_quality_or_peer_exclusions':dict(excluded)},
  'field_coverage':dict(coverage),'peer_policy':{'primary':'SAME_PROPERTY_CLASS','minimum_peer_count':20,'core_relationship':'BOTTOM_10_PERCENT_IMPROVEMENT_TO_LAND_RATIO_AND_TOP_10_PERCENT_LAND_SHARE_WITHIN_COMPATIBLE_CLASS','acreage_is_separate_context_not_universal_gate':True,'living_sqft_is_corroboration_not_required':True},
  'candidates':candidates[:40],
  'policy':{'one_fact_not_seller':True,'seller_intent_inferred':False,'missing_information_nonblocking':True,'unknown_valid_state':True,'route_kill_never_equals_property_kill':True,'closed_class_210_routes_reopened':False,'score_or_rank_exposed':False},
  'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},
  'next_if_verified':'INTEGRATE SURVIVING LAND_PROPERTY_UTILIZATION ROUTES INTO FIND1 PROPERTY PROFILES; THEN APPLY TARGETED CAUSAL_KILL RESEARCH ONLY WHERE A SINGLE FACT HAS HIGH INFORMATION VALUE'}
