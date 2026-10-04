#!/usr/bin/env python3
import os, json, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from property_research_router_v1 import build_property_research_router_v1

VERSION="PROPERTY_SOURCE_SEMANTICS_AUDIT_V1"
MARKET="WESTHAMPTON_BEACH_NY"
FAMILIES=("PROPERTY_CONTEXT","ASSESSMENT_CONTEXT")
TARGETS={
 "market_value":["assessment_market_value","market_value","estimated_market_value","full_market_value"],
 "full_baths":["full_baths","bathrooms","baths"],
 "assessment_total":["assessment_total","total_assessment","assessed_total","total_assessed_value","assessed_value"],
 "land_assessment":["land_assessment","assessed_land","land_assessed_value"],
 "property_class":["property_class","class","propertyclass","landuse","land_use","use_class","property_type"],
 "building_style":["building_style","style"],
}

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
def _leaf(k):return k.split(".")[-1]
def _num(v):
 try:
  if v is None or isinstance(v,bool):return None
  x=float(str(v).strip().replace(",","").replace("$",""));return x if math.isfinite(x) else None
 except:return None

def build_property_source_semantics_audit_v1():
 router=build_property_research_router_v1()
 cases=router.get("routed_cases") or []
 case_ids={c.get("parcel_id") for c in cases if c.get("parcel_id")}
 import psycopg
 conn=psycopg.connect(os.environ["DATABASE_URL"])
 try:
  cur=conn.cursor();cur.execute("""SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
   WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s) ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,list(FAMILIES)))
  rows=cur.fetchall()
 finally:conn.close()

 parcel_fields=defaultdict(lambda:defaultdict(list)); family_keys=defaultdict(Counter)
 for pid,fam,pj in rows:
  f=_flat(_payload(pj))
  for k,v in f.items():
   family_keys[fam][_leaf(k)]+=1
   for logical,aliases in TARGETS.items():
    if _leaf(k) in aliases and v not in (None,""):
     parcel_fields[pid][logical].append({"source_family":fam,"source_key":k,"raw_value":v})

 audits={}; population=len(parcel_fields)
 for logical,aliases in TARGETS.items():
  key_counts=Counter(); fam_counts=Counter(); present=zero=numeric=conflicts=0; examples=[]
  case_present=case_zero=0
  for pid,fields in parcel_fields.items():
   vals=fields.get(logical,[])
   if vals:
    present+=1
    nums=[]
    for x in vals:
     key_counts[_leaf(x["source_key"])]+=1;fam_counts[x["source_family"]]+=1
     n=_num(x["raw_value"])
     if n is not None: nums.append(n);numeric+=1
    if nums and all(n==0 for n in nums):zero+=1
    canon={str(x["raw_value"]).strip() for x in vals}
    if len(canon)>1: conflicts+=1
    if len(examples)<5:examples.append({"parcel_id":pid,"observations":vals[:6]})
   if pid in case_ids:
    if vals:case_present+=1
    nums=[_num(x["raw_value"]) for x in vals if _num(x["raw_value"]) is not None]
    if nums and all(n==0 for n in nums):case_zero+=1
  # conservative machine-consumption rule; audit describes semantics, it does not invent meaning.
  if present==0: state="STRUCTURALLY_MISSING"
  elif logical=="market_value" and zero==present: state="PRESENT_BUT_ZERO_POPULATION_WIDE_DO_NOT_USE_AS_VALUE"
  elif conflicts>0: state="MULTIPLE_SOURCE_VALUES_REQUIRE_SEMANTIC_REVIEW"
  elif logical=="full_baths" and zero>0: state="USABLE_WITH_ZERO_VALUE_PLAUSIBILITY_WARNING"
  elif logical in ("assessment_total","land_assessment") and present>0: state="USABLE_AS_ASSESSMENT_COMPONENT_NOT_MARKET_PRICE"
  elif logical=="property_class": state="USABLE_AS_SOURCE_CLASSIFICATION_VERIFY_CLASS_DICTIONARY_FOR_MEANING"
  else: state="PRESENT_SEMANTICS_NOT_FULLY_DOCUMENTED"
  audits[logical]={"aliases_examined":aliases,"parcels_present":present,"population_parcels_seen":population,"zero_only_parcels":zero,"conflicting_multi_source_parcels":conflicts,"source_leaf_keys":dict(key_counts),"source_families":dict(fam_counts),"routed_41_present":case_present,"routed_41_zero_only":case_zero,"consumption_state":state,"sample_raw_observations":examples}

 mv=audits["market_value"]
 conclusions=[]
 if mv["parcels_present"] and mv["zero_only_parcels"]==mv["parcels_present"]:
  conclusions.append("MARKET_VALUE_NORMALIZED_FIELD_IS_NOT_VALID_OPPORTUNITY_EVIDENCE_IN_CURRENT_DATASET_BECAUSE_ALL_OBSERVED_SOURCE_VALUES_ARE_ZERO")
 conclusions += [
  "ASSESSMENT_TOTAL_AND_LAND_ASSESSMENT_MAY_BE_USED_AS_ASSESSMENT_COMPONENTS_BUT_NOT_SILENTLY_RELABELED_AS_MARKET_PRICE",
  "ZERO_FULL_BATHS_IS_A_PLAUSIBILITY_WARNING_NOT_AN_OPPORTUNITY_SIGNAL",
  "PROPERTY_CLASS_MAY_GROUP_PEERS_BUT_CLASS_CODE_MEANING_REMAINS_A_SEPARATE_SEMANTIC_LOOKUP",
  "DATA_QUALITY_FLAGS_MUST_NOT_APPEAR_IN_WHY_PMI_FOUND_IT_UNLESS_LATER_VERIFIED_AS_REAL_PROPERTY_FACTS"
 ]
 return {"status":"ok","version":VERSION,"mode":"READ_ONLY_SOURCE_SEMANTICS_AUDIT","generated_at":datetime.now(timezone.utc).isoformat(),
  "source_checkpoint":{"router_version":router.get("version"),"routed_cases":len(cases),"router_reconciliation":router.get("reconciliation")},
  "population":{"ledger_rows_examined":len(rows),"parcels_seen":population,"families":list(FAMILIES)},"field_audits":audits,"conclusions":conclusions,
  "policy":{"raw_source_keys_before_semantic_inference":True,"data_quality_is_not_opportunity_evidence":True,"missing_information_nonblocking":True,"seller_intent_inferred":False},
  "database_writes":0,"guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
  "next_if_verified":"APPLY_CONSUMPTION_RULES_TO_THE_41_CASES_THEN_RUN_THE_FIRST_TARGETED_FACT_RESOLUTION_TEST_ON_THE_DOMINANT_RESEARCH_ROUTE"}
