#!/usr/bin/env python3
import os, json, math, statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone

VERSION="PROPERTY_ANOMALY_EXPLAINER_V1"
MARKET="WESTHAMPTON_BEACH_NY"
FAMILIES=("PROPERTY_CONTEXT","ASSESSMENT_CONTEXT")
ALIASES={
 "address":["property_address","parcel_address","address","fulladdress","full_address","site_address","situs_address"],
 "property_class":["property_class","class","propertyclass","landuse","land_use","use_class","property_type"],
 "acres":["acres","acreage","lot_acres","parcel_acres"],
 "assessment_total":["assessment_total","total_assessment","assessed_total","total_assessed_value","assessed_value"],
 "market_value":["assessment_market_value","market_value","estimated_market_value","full_market_value"],
 "land_assessment":["land_assessment","assessed_land","land_assessed_value"],
 "year_built":["year_built","yearbuilt"],"living_sqft":["living_sqft","living_area","sqft","square_feet"],
 "bedrooms":["bedrooms","beds"],"full_baths":["full_baths","bathrooms","baths"],"building_style":["building_style","style"]}
NUMERIC={"acres","assessment_total","market_value","land_assessment","year_built","living_sqft","bedrooms","full_baths"}

def _payload(v):
 if isinstance(v,dict): return v
 try:
  x=json.loads(v) if v else {}; return x if isinstance(x,dict) else {}
 except Exception:return {}
def _flat(d,prefix=""):
 out={}
 for k,v in d.items():
  key=(prefix+str(k)).lower().strip()
  if isinstance(v,dict):out.update(_flat(v,key+"."))
  else:out[key]=v
 return out
def _pick(f,aa):
 for a in aa:
  if a in f and f[a] not in (None,""):return f[a]
 for a in aa:
  h=[v for k,v in f.items() if k.split(".")[-1]==a and v not in (None,"")]
  if h:return h[0]
 return None
def _num(v):
 try:
  if v is None or isinstance(v,bool):return None
  x=float(str(v).strip().replace(",","").replace("$","")); return x if math.isfinite(x) else None
 except:return None
def _med(x):return statistics.median(x) if x else None
def _mad(x):
 if not x:return None
 m=_med(x);return _med([abs(v-m) for v in x])
def _rz(x,xs):
 if x is None or len(xs)<5:return None
 m=_med(xs);d=_mad(xs)
 return None if d in (None,0) else .67448975*(x-m)/d
def _pct(xs,x):
 if not xs or x is None:return None
 s=sorted(xs);return (sum(v<x for v in s)+.5*sum(v==x for v in s))/len(s)
def _band(v,pct=.25,min_abs=None):
 if v is None:return None
 w=max(abs(v)*pct,min_abs or 0);return (v-w,v+w)

def build_property_anomaly_explainer_v1():
 import psycopg
 conn=psycopg.connect(os.environ["DATABASE_URL"])
 try:
  cur=conn.cursor();cur.execute("""SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
   WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s) ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,list(FAMILIES)))
  rows=cur.fetchall()
 finally:conn.close()
 by=defaultdict(dict)
 for pid,fam,pj in rows:
  by[pid].setdefault(fam,{})
  for k,v in _flat(_payload(pj)).items():
   if v not in (None,"") and k not in by[pid][fam]:by[pid][fam][k]=v
 recs=[];cov=Counter()
 for pid,fams in by.items():
  merged={}
  for fam in FAMILIES:merged.update(fams.get(fam,{}))
  r={"parcel_id":pid}
  for k,aa in ALIASES.items():
   raw=_pick(merged,aa);r[k]=_num(raw) if k in NUMERIC else (str(raw).strip() if raw not in (None,"") else None)
   if r[k] is not None:cov[k]+=1
  if r["acres"] is not None and r["acres"]<=0:r["acres"]=None
  if r["assessment_total"] is not None and r["land_assessment"] is not None and r["assessment_total"]>=r["land_assessment"]:
   r["improvement_assessment"]=r["assessment_total"]-r["land_assessment"];cov["improvement_assessment"]+=1
  else:r["improvement_assessment"]=None
  if r["land_assessment"] not in (None,0) and r["improvement_assessment"] is not None:r["improvement_land_ratio"]=r["improvement_assessment"]/r["land_assessment"]
  else:r["improvement_land_ratio"]=None
  recs.append(r)
 groups=defaultdict(list)
 for r in recs:
  if r["property_class"]:groups[r["property_class"]].append(r)
 base=[]
 for r in recs:
  peers=groups.get(r["property_class"],[])
  ratios=[p["improvement_land_ratio"] for p in peers if p["improvement_land_ratio"] is not None]
  z=_rz(r["improvement_land_ratio"],ratios) if len(peers)>=20 else None
  if z is not None and abs(z)>=3.5:
   x=dict(r);x["base_z"]=z;x["class_peer_count"]=len(peers);x["class_ratio_median"]=_med(ratios);base.append(x)

 explained=Counter();survivors=[]
 for r in base:
  peers=groups[r["property_class"]]
  # Physical comparables: same class, with living area within +/-25%; year within +/-15 when both are available.
  comparable=[]
  sqft_band=_band(r["living_sqft"],.25,250) if r["living_sqft"] else None
  for p in peers:
   if p["parcel_id"]==r["parcel_id"] or p["improvement_land_ratio"] is None:continue
   if sqft_band and p["living_sqft"] is not None and not (sqft_band[0]<=p["living_sqft"]<=sqft_band[1]):continue
   if r["year_built"] is not None and p["year_built"] is not None and abs(p["year_built"]-r["year_built"])>15:continue
   comparable.append(p)
  cr=[p["improvement_land_ratio"] for p in comparable]
  cz=_rz(r["improvement_land_ratio"],cr) if len(cr)>=20 else None
  sqft_pct=_pct([p["living_sqft"] for p in peers if p["living_sqft"] is not None],r["living_sqft"])
  year_pct=_pct([p["year_built"] for p in peers if p["year_built"] is not None],r["year_built"])
  impr_pct=_pct([p["improvement_assessment"] for p in peers if p["improvement_assessment"] is not None],r["improvement_assessment"])
  land_pct=_pct([p["land_assessment"] for p in peers if p["land_assessment"] is not None],r["land_assessment"])
  reasons=[]
  if sqft_pct is not None and sqft_pct>=.90:reasons.append("LARGE_STRUCTURE_RELATIVE_TO_CLASS")
  if year_pct is not None and year_pct>=.90:reasons.append("NEWER_STRUCTURE_RELATIVE_TO_CLASS")
  if impr_pct is not None and impr_pct>=.90:reasons.append("HIGH_IMPROVEMENT_ASSESSMENT_RELATIVE_TO_CLASS")
  if land_pct is not None and land_pct<=.10:reasons.append("LOW_LAND_ASSESSMENT_RELATIVE_TO_CLASS")
  if cz is not None and abs(cz)<2.5:
   disposition="EXPLAINED_BY_PHYSICAL_PEERS";explained[disposition]+=1
  elif len(cr)<20:
   disposition="NEEDS_CEECEE_VERIFICATION";explained[disposition]+=1
  else:
   disposition="SURVIVES_PHYSICAL_CONTEXT";explained[disposition]+=1
  item={"parcel_id":r["parcel_id"],"property_address":r["address"],"property_class":r["property_class"],
   "base_anomaly":{"improvement_to_land_ratio":round(r["improvement_land_ratio"],4),"class_peer_median":round(r["class_ratio_median"],4),"robust_z":round(r["base_z"],2),"class_peer_count":r["class_peer_count"]},
   "physical_context":{"year_built":r["year_built"],"living_sqft":r["living_sqft"],"bedrooms":r["bedrooms"],"full_baths":r["full_baths"],"building_style":r["building_style"],"acres":r["acres"],"land_assessment":r["land_assessment"],"improvement_assessment":r["improvement_assessment"],"market_value":r["market_value"],"context_flags":reasons},
   "physical_peer_test":{"peer_count":len(cr),"robust_z":round(cz,2) if cz is not None else None,"definition":"SAME_CLASS + LIVING_SQFT_WITHIN_25_PERCENT + YEAR_BUILT_WITHIN_15_YEARS_WHEN_AVAILABLE"},
   "disposition":disposition,"seller_intent":"UNKNOWN","contact_authorized":False,
   "missing_information_nonblocking":True,
   "next_research_question":"What verified property/site/use fact explains the remaining land-versus-improvement mismatch?" if disposition!="EXPLAINED_BY_PHYSICAL_PEERS" else "No manual follow-up yet; anomaly is materially explained by physical peers."}
  if disposition!="EXPLAINED_BY_PHYSICAL_PEERS":survivors.append(item)
 # Inspection order is diagnostic, not seller rank: unresolved/surviving then absolute physical-peer z.
 survivors.sort(key=lambda x:(0 if x["disposition"]=="SURVIVES_PHYSICAL_CONTEXT" else 1,-abs(x["physical_peer_test"]["robust_z"] or 0),x["parcel_id"]))
 return {"status":"ok","version":VERSION,"mode":"READ_ONLY_ANOMALY_EXPLANATION_LAB","generated_at":datetime.now(timezone.utc).isoformat(),
  "summary":{"full_universe":len(recs),"base_a4_anomalies":len(base),"dispositions":dict(explained),"surviving_or_verification_cases":len(survivors)},
  "field_coverage":dict(cov),"explanation_policy":{"purpose":"KILL_EXPLAINABLE_FALSE_POSITIVES_BEFORE_HUMAN_REVIEW","missing_information_nonblocking":True,"needs_ceecee_verification_is_valid_state":True,"manual_review_is_exception_path_not_bulk_queue":True,"seller_intent_inferred":False},
  "inspection_cases":survivors[:30],"database_writes":0,
  "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
  "next_if_verified":"REVIEW_SURVIVING_CASES_AND_DECIDE_WHICH_MISSING_FACT_HAS_HIGHEST_INFORMATION_VALUE"}
