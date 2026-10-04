#!/usr/bin/env python3
import os,re,json,math,statistics
from collections import defaultdict
from datetime import datetime,timezone
VERSION='FIND20'; MARKET='WESTHAMPTON_BEACH_NY'
FIND1_IDS=set('''0905013000400014000 0905018000100001000 0905003000100056000 0905018000100028000 0905017000500015000 0905008000300039000 0905012000300007000 0905002000200013000 0905008000200015001 0905011000300031000 0905010000600023000 0905006000300004035 0905008000100032002 0905015000400001000 0905012000400047002 0905015000300007001 0905012000200016000 0905015000200025000 0905006000100023000 0905008000300008003 0905011000100004000 0905009000200014000 0905014000100019000 0905003000200027003 0905006000100004002 0905015000300002001 0905008000100024000 0905006000100007000 0905006000200011005 0905002000200018000 0905009000300017009 0905011000200044001 0905008000200015002 0905013000100024003 0905014000100009000 0905005000300022000 0905011000300011000 0905013000400008001 0905015000200026003 0905015000300005001 0905017000300009000'''.split())
ALIASES={'address':['property_address','parcel_address','address','fulladdress','full_address','site_address','situs_address'],'property_class':['property_class','class','propertyclass','landuse','land_use','use_class','property_type'],'acres':['acres','acreage','lot_acres','parcel_acres'],'assessment_total':['assessment_total','total_assessment','assessed_total','total_assessed_value','assessed_value'],'land_assessment':['land_assessment','assessed_land','land_assessed_value'],'year_built':['year_built','yearbuilt'],'living_sqft':['living_sqft','living_area','sqft','square_feet']}
SUFFIX={'ROAD':'RD','AVENUE':'AVE','STREET':'ST','LANE':'LN','DRIVE':'DR','COURT':'CT','HIGHWAY':'HWY','BOULEVARD':'BLVD','PLACE':'PL','TERRACE':'TER'}
def _payload(v):
 if isinstance(v,dict):return v
 try:
  x=json.loads(v) if v else {};return x if isinstance(x,dict) else {}
 except:return {}
def _flat(d):
 out={}
 def walk(x):
  if not isinstance(x,dict):return
  for k,v in x.items():
   k=str(k).lower().strip()
   if isinstance(v,dict):walk(v)
   elif k not in out and v not in (None,''):out[k]=v
 walk(d);return out
def _pick(f,aa):
 for a in aa:
  if f.get(a) not in (None,''):return f[a]
def _num(v):
 try:
  if v is None or isinstance(v,bool):return None
  x=float(str(v).replace(',','').replace('$','').strip());return x if math.isfinite(x) else None
 except:return None
def _pct(xs,x):
 if x is None or not xs:return None
 s=sorted(xs);return (sum(v<x for v in s)+.5*sum(v==x for v in s))/len(s)
def _street(a):
 if not a:return None
 s=re.sub(r'[^A-Z0-9 ]+',' ',str(a).upper()).strip();p=s.split()
 if p and re.match(r'^\d+[A-Z]?$',p[0]):p=p[1:]
 if p and p[-1] in SUFFIX:p[-1]=SUFFIX[p[-1]]
 return ' '.join(p) or None
def _records():
 import psycopg
 c=psycopg.connect(os.environ['DATABASE_URL'])
 try:
  q=c.cursor();q.execute('''SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s) ORDER BY parcel_id,evidence_family,evidence_key''',(MARKET,['PROPERTY_CONTEXT','ASSESSMENT_CONTEXT']));rows=q.fetchall()
 finally:c.close()
 by=defaultdict(dict)
 for pid,fam,pj in rows:
  for k,v in _flat(_payload(pj)).items():
   if k not in by[str(pid)] and v not in (None,''):by[str(pid)][k]=v
 rec=[]
 for pid,m in by.items():
  r={'parcel_id':pid}
  for k,a in ALIASES.items():
   v=_pick(m,a);r[k]=_num(v) if k in ('acres','assessment_total','land_assessment','year_built','living_sqft') else (str(v).strip() if v not in (None,'') else None)
  t,l=r['assessment_total'],r['land_assessment'];r['improvement_assessment']=t-l if t is not None and l is not None and t>=l else None
  r['improvement_to_land']=r['improvement_assessment']/l if l not in (None,0) and r['improvement_assessment'] is not None else None;r['land_share']=l/t if t not in (None,0) and l is not None else None;r['street_context']=_street(r['address']);rec.append(r)
 return rec
def _baseline_and_find19(rec):
 classes=defaultdict(list);streets=defaultdict(list);groups=defaultdict(list)
 for r in rec:
  if r['property_class']:classes[r['property_class']].append(r)
  if r['street_context'] and r['year_built'] and 1600<=r['year_built']<=datetime.now().year+1:streets[r['street_context']].append(r)
  if r['street_context'] and r['property_class'] and r['acres'] and r['acres']>0:groups[(r['street_context'],r['property_class'])].append(r)
 # FIND2 exact membership
 f2=set()
 for r in rec:
  peers=classes.get(r['property_class'],[])
  if len(peers)<20 or r['improvement_to_land'] is None or r['land_share'] is None:continue
  rp=_pct([p['improvement_to_land'] for p in peers if p['improvement_to_land'] is not None],r['improvement_to_land']);sp=_pct([p['land_share'] for p in peers if p['land_share'] is not None],r['land_share'])
  if rp is not None and sp is not None and rp<=.10 and sp>=.90:f2.add(r['parcel_id'])
 base=set(FIND1_IDS)|f2
 # FIND12 exact membership, then promotion into FIND13
 f12=set()
 for r in rec:
  if not r['street_context'] or r['year_built'] is None or not (1600<=r['year_built']<=datetime.now().year+1):continue
  peers=[x for x in streets[r['street_context']] if x['parcel_id']!=r['parcel_id']]
  if len(peers)<8:continue
  yrs=[x['year_built'] for x in peers];med=statistics.median(yrs);ap=_pct(yrs,r['year_built']);newer=[x for x in peers if x['year_built']>=r['year_built']+20]
  if ap is not None and ap<=.20 and med-r['year_built']>=20 and len(newer)>=3:f12.add(r['parcel_id'])
 base|=f12
 find13_count=len(base)
 # FIND14 exact membership; promoted novel cases expand to 226
 f14=set()
 for r in rec:
  if not r['street_context'] or r['year_built'] is None or not (1600<=r['year_built']<=datetime.now().year+1):continue
  peers=[x for x in streets[r['street_context']] if x['parcel_id']!=r['parcel_id']]
  if len(peers)<8 or r['year_built']>=2000:continue
  recent=[x for x in peers if x['year_built']>=2015]
  if len(recent)>=3 and len(recent)/len(peers)>=.25:f14.add(r['parcel_id'])
 base|=f14
 pre16_count=len(base)
 # FIND16 exact membership; only novel cases expand protected universe to 230
 f16=set()
 for r in rec:
  peers=classes.get(r['property_class'],[])
  if len(peers)<20 or r['land_share'] is None or r['improvement_to_land'] is None or r['year_built'] is None or not r['street_context'] or r['year_built']>=2000:continue
  rp=_pct([p['improvement_to_land'] for p in peers if p['improvement_to_land'] is not None],r['improvement_to_land']);sp=_pct([p['land_share'] for p in peers if p['land_share'] is not None],r['land_share']);sq=[p['living_sqft'] for p in peers if p['living_sqft'] and p['living_sqft']>0];qp=_pct(sq,r['living_sqft']) if r['living_sqft'] and r['living_sqft']>0 else None
  if sp is None or sp<.75 or not ((rp is not None and rp<=.25) or (qp is not None and qp<=.35)):continue
  peers2=[x for x in streets[r['street_context']] if x['parcel_id']!=r['parcel_id']]
  if len(peers2)<8:continue
  recent=[x for x in peers2 if x['year_built']>=2015]
  if len(recent)>=2 and len(recent)/len(peers2)>=.20:f16.add(r['parcel_id'])
 base|=f16
 # FIND19 exact membership and diagnostic payload
 f19=[]
 for r in rec:
  if not r['street_context'] or not r['property_class'] or not r['acres'] or r['acres']<=0:continue
  peers=[x for x in groups[(r['street_context'],r['property_class'])] if x['parcel_id']!=r['parcel_id']]
  if len(peers)<8:continue
  acres=[x['acres'] for x in peers if x['acres'] and x['acres']>0]
  if len(acres)<8:continue
  med=statistics.median(acres);ap=_pct(acres,r['acres'])
  if ap is None or ap<.90 or med<=0 or r['acres']<med*1.5:continue
  cor=[]
  if r['improvement_assessment'] is not None and r['improvement_assessment']<=0:cor.append('ZERO_ASSESSED_IMPROVEMENT_COMPONENT')
  if r['land_share'] is not None and r['land_share']>=.80:cor.append('LAND_HEAVY_ASSESSMENT_RELATIONSHIP')
  sq=[x['living_sqft'] for x in peers if x['living_sqft'] and x['living_sqft']>0];qp=_pct(sq,r['living_sqft']) if r['living_sqft'] and r['living_sqft']>0 and sq else None
  if qp is not None and qp<=.25:cor.append('SMALL_IMPROVEMENT_RELATIVE_TO_LOCAL_COMPATIBLE_CONTEXT')
  if cor:f19.append({'parcel_id':r['parcel_id'],'property_address':r['address'],'property_class':r['property_class'],'corroboration':cor,'local_context':{'street_context':r['street_context'],'subject_acres':round(r['acres'],6),'peer_median_acres':round(med,6),'subject_to_peer_median_acreage_multiple':round(r['acres']/med,6)}})
 f19.sort(key=lambda x:(-x['local_context']['subject_to_peer_median_acreage_multiple'],-len(x['corroboration']),x['parcel_id']))
 return base,f19,{'find1':len(FIND1_IDS),'find2':len(f2),'find13_union':find13_count,'find14_candidates':len(f14),'pre_find16_union':pre16_count,'find16_candidates':len(f16)}
def build_find20():
 rec=_records();base,f19,checks=_baseline_and_find19(rec)
 if len(base)!=230:raise RuntimeError(f'protected discovery universe reconstruction mismatch: expected 230, got {len(base)}')
 out=[];nov=0;over=0
 for c in f19:
  is_new=c['parcel_id'] not in base
  nov+=int(is_new);over+=int(not is_new)
  x=dict(c);x.update({'opportunity_family':'OU_007_LOT_LINE_RECONFIGURATION_OPPORTUNITY','novel_to_existing_230_property_universe':is_new,'existing_discovery_universe_coverage':not is_new,'integration_effect':'ADD_NEW_PROPERTY_TO_DISCOVERY_UNIVERSE' if is_new else 'ADD_DISTINCT_OU_007_WHY_FOUND_CORROBORATION_TO_EXISTING_PROPERTY','state':'NOVEL_DISCOVERY_SUPPORTED_NOT_PROVEN' if is_new else 'DISTINCT_CORROBORATION_SUPPORTED_NOT_PROVEN','seller_intent':'UNKNOWN','contact_authorized':False,'next_best_question':'Do not fetch geometry yet. First preserve OU_007 as a WHY_FOUND reason; obtain one geometry/frontage/access/legal-lot fact only if this property later advances enough that the answer can change the decision.'});out.append(x)
 return {'status':'ok','version':VERSION,'mode':'READ_ONLY_FIND19_NOVELTY_AND_CORROBORATION_INTEGRATION_GATE','generated_at':datetime.now(timezone.utc).isoformat(),'purpose':'DETERMINE_WHETHER_FIND19_OU_007_ADDS_NOVEL_PROPERTY_DISCOVERY_OR_DISTINCT_CORROBORATION_VERSUS_THE_PROTECTED_230_PROPERTY_UNIVERSE','architecture':{'protected_pre_find19_discovery_universe':230,'historical_find1_membership_frozen_from_promoted_checkpoint':True,'other_prior_membership_reconstructed_from_promoted_existing_evidence_rules':True,'baseline_cardinality_must_equal_230':True,'no_external_lookup':True,'no_geometry_or_frontage_fetch':True},'reconstruction_checks':checks,'summary':{'working_property_universe':len(rec),'protected_pre_find19_discovery_universe':len(base),'find19_candidates_reconstructed':len(f19),'novel_properties_added_by_ou_007':nov,'existing_properties_with_distinct_ou_007_corroboration':over,'post_find20_discovery_universe':len(base)+nov},'cases':out,'case_payload':{'total':len(out),'returned':len(out),'complete':True,'display_policy':'NOVELTY_THEN_CORROBORATION_DIAGNOSTIC_NOT_OPERATOR_RANKING'},'promotion_decision':{'ou_007':'PROMOTE' if nov>0 or over>0 else 'KILL','reason':'OU_007_ADDS_NOVEL_DISCOVERY_AND_OR_DISTINCT_PROPERTY_LEVEL_CORROBORATION' if nov>0 or over>0 else 'NO_INFORMATION_GAIN'},'interpretation_policy':{'data_serves_decision':True,'novel_property_and_new_reason_are_distinct_values':True,'corroboration_does_not_equal_seller_intent':True,'reconfiguration_not_subdivision':True,'street_context_not_true_adjacency':True,'geometry_only_if_later_material':True,'route_kill_never_equals_property_kill':True,'unknown_valid_state':True},'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False},'next_if_verified':'IF OU_007 IS PROMOTED, UPDATE THE CONCEPTUAL DISCOVERY UNIVERSE BY NOVEL COUNT AND PRESERVE OU_007 AS A DISTINCT WHY_FOUND RAIL. THEN MOVE TO ANOTHER INDEPENDENT OPPORTUNITY FAMILY; DO NOT AUTOMATICALLY FETCH GEOMETRY FOR ALL OU_007 CASES.'}
if __name__=='__main__':print(json.dumps(build_find20(),indent=2,sort_keys=True))
