#!/usr/bin/env python3
import os, json, math, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from assessment_improvement_fact_resolution_v1 import build_assessment_improvement_fact_resolution_v1

VERSION="TARGETED_PROPERTY_ASSESSMENT_LOOKUP_V1"
MARKET="WESTHAMPTON_BEACH_NY"
TARGET_PARCEL="0905017000500015000"
TARGET_ADDRESS="429A DUNE RD"
CORE_FAMILIES=("PROPERTY_CONTEXT","ASSESSMENT_CONTEXT")

ALIASES={
 "address":["property_address","parcel_address","address","fulladdress","full_address","site_address","situs_address"],
 "property_class":["property_class","class","propertyclass","landuse","land_use","use_class","property_type"],
 "acres":["acres","acreage","lot_acres","parcel_acres"],
 "assessed_total":["assessment_total","total_assessment","assessed_total","total_assessed_value","assessed_value"],
 "assessed_land":["land_assessment","assessed_land","land_assessed_value"],
 "full_market_value":["assessment_market_value","market_value","estimated_market_value","full_market_value"],
 "year_built":["year_built","yearbuilt"],
 "living_sqft":["living_sqft","living_area","sqft","square_feet"],
 "bedrooms":["bedrooms","beds"],
 "full_baths":["full_baths","bathrooms","baths"],
 "building_style":["building_style","style"]
}
NUMERIC={"acres","assessed_total","assessed_land","full_market_value","year_built","living_sqft","bedrooms","full_baths"}

def _payload(v):
    if isinstance(v,dict): return v
    try:
        x=json.loads(v) if v else {}
        return x if isinstance(x,dict) else {}
    except Exception: return {}

def _flat(d,prefix=""):
    out={}
    for k,v in d.items():
        key=(prefix+str(k)).lower().strip()
        if isinstance(v,dict): out.update(_flat(v,key+"."))
        else: out[key]=v
    return out

def _pick(flat, aliases):
    for a in aliases:
        if a in flat and flat[a] not in (None,""): return flat[a],a
    for a in aliases:
        for k,v in flat.items():
            if k.split(".")[-1]==a and v not in (None,""): return v,k
    return None,None

def _num(v):
    try:
        if v is None or isinstance(v,bool): return None
        x=float(str(v).replace(",","").replace("$","").strip())
        return x if math.isfinite(x) else None
    except Exception: return None

def _median(xs): return statistics.median(xs) if xs else None

def build_targeted_property_assessment_lookup_v1():
    checkpoint=build_assessment_improvement_fact_resolution_v1()
    target=next((x for x in checkpoint.get("resolved_cases",[]) if x.get("parcel_id")==TARGET_PARCEL),None)
    if not target:
        return {"status":"target_not_found","version":VERSION,"target_parcel":TARGET_PARCEL,"database_writes":0,
                "guards":{"database_writes":False,"external_calls":False,"v19v_touched":False,"contact_authorized":False}}

    import psycopg
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT evidence_family,evidence_key,payload_json FROM evidence_ledger
                       WHERE market_code=%s AND parcel_id=%s AND is_current=1
                       ORDER BY evidence_family,evidence_key""",(MARKET,TARGET_PARCEL))
        target_rows=cur.fetchall()
        cur.execute("""SELECT parcel_id,evidence_family,payload_json FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1 AND evidence_family=ANY(%s)
                       ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,list(CORE_FAMILIES)))
        core_rows=cur.fetchall()
    finally:
        conn.close()

    family_counts=Counter(r[0] for r in target_rows)
    core_by_family=defaultdict(dict)
    raw_key_inventory=defaultdict(list)
    for fam,key,pj in target_rows:
        flat=_flat(_payload(pj))
        raw_key_inventory[fam].extend(sorted(flat.keys()))
        if fam in CORE_FAMILIES:
            for k,v in flat.items():
                if v not in (None,"") and k not in core_by_family[fam]: core_by_family[fam][k]=v
    merged={}
    for fam in CORE_FAMILIES: merged.update(core_by_family.get(fam,{}))
    facts={}; source_keys={}
    for name,aliases in ALIASES.items():
        raw,key=_pick(merged,aliases)
        facts[name]=_num(raw) if name in NUMERIC else (str(raw).strip() if raw not in (None,"") else None)
        source_keys[name]=key
    if facts["assessed_total"] is not None and facts["assessed_land"] is not None and facts["assessed_total"]>=facts["assessed_land"]:
        facts["improvement_assessment"]=facts["assessed_total"]-facts["assessed_land"]
    else: facts["improvement_assessment"]=None
    if facts["assessed_land"] not in (None,0) and facts["improvement_assessment"] is not None:
        facts["improvement_to_land_ratio"]=facts["improvement_assessment"]/facts["assessed_land"]
    else: facts["improvement_to_land_ratio"]=None

    # Rebuild same-class peer distribution from audited assessment components only.
    parcels=defaultdict(dict)
    for pid,fam,pj in core_rows:
        parcels[pid].setdefault(fam,{})
        for k,v in _flat(_payload(pj)).items():
            if v not in (None,"") and k not in parcels[pid][fam]: parcels[pid][fam][k]=v
    peer_ratios=[]; peer_components=[]
    for pid,fams in parcels.items():
        m={}
        for fam in CORE_FAMILIES:m.update(fams.get(fam,{}))
        pc,_=_pick(m,ALIASES["property_class"])
        if str(pc).strip()!=str(facts["property_class"]): continue
        t,_=_pick(m,ALIASES["assessed_total"]); l,_=_pick(m,ALIASES["assessed_land"])
        t=_num(t);l=_num(l)
        if t is None or l in (None,0) or t<l: continue
        imp=t-l; ratio=imp/l
        peer_ratios.append(ratio);peer_components.append((pid,t,l,imp,ratio))
    med=_median(peer_ratios)
    target_ratio=facts["improvement_to_land_ratio"]
    percentile=None
    if peer_ratios and target_ratio is not None:
        percentile=(sum(v<target_ratio for v in peer_ratios)+0.5*sum(v==target_ratio for v in peer_ratios))/len(peer_ratios)

    # Existing evidence can validate the components and reproduce the anomaly, but cannot
    # establish the causal property fact if no richer improvement/use record exists.
    semantic_core=set(CORE_FAMILIES)
    additional_families=sorted(set(family_counts)-semantic_core)
    # Ownership/title families are intentionally not treated as causal explanations for this property anomaly.
    noncausal=[f for f in additional_families if f in {"OWNERSHIP","TRANSFER_TITLE"}]
    potentially_property_causal=[f for f in additional_families if f not in {"OWNERSHIP","TRANSFER_TITLE"}]
    has_richer_causal=bool(potentially_property_causal)
    resolution="EXISTING_EVIDENCE_REPRODUCES_ANOMALY_BUT_DOES_NOT_EXPLAIN_PROPERTY_CAUSE" if not has_richer_causal else "ADDITIONAL_EXISTING_PROPERTY_EVIDENCE_AVAILABLE_FOR_NEXT_INSPECTION"

    return {
      "status":"ok",
      "version":VERSION,
      "mode":"READ_ONLY_SINGLE_PROPERTY_EXISTING_EVIDENCE_LOOKUP",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "source_checkpoint":{"version":checkpoint.get("version"),"target_route":"TARGETED_PROPERTY_ASSESSMENT_FACT_LOOKUP"},
      "target":{"parcel_id":TARGET_PARCEL,"property_address":facts.get("address") or TARGET_ADDRESS,"property_class":facts.get("property_class")},
      "existing_evidence_inventory":{"current_rows":len(target_rows),"families":dict(sorted(family_counts.items())),"additional_noncausal_families":noncausal,"additional_potentially_property_causal_families":potentially_property_causal},
      "verified_property_assessment_facts":facts,
      "source_keys_used":source_keys,
      "same_class_assessment_context":{"peer_count":len(peer_ratios),"peer_median_improvement_to_land_ratio":round(med,6) if med is not None else None,"target_improvement_to_land_ratio":round(target_ratio,6) if target_ratio is not None else None,"target_percentile":round(percentile,6) if percentile is not None else None},
      "fact_resolution":{
        "state":resolution,
        "what_existing_evidence_proves":["ASSESSED_TOTAL_AND_ASSESSED_LAND_ARE_PRESENT_FOR_TARGET","IMPROVEMENT_COMPONENT_IS_DERIVABLE_WITHOUT_MARKET_VALUE","TARGET_REMAINS_EXTREME_RELATIVE_TO_SAME_CLASS_ASSESSMENT_RATIO"],
        "what_existing_evidence_does_not_prove":"WHY_THIS_PROPERTY_HAS_THE_OBSERVED_LAND_VERSUS_IMPROVEMENT_ALLOCATION",
        "title_or_ownership_used_as_explanation":False,
        "seller_intent":"UNKNOWN",
        "why_pmi_found_it":"LAND_VERSUS_IMPROVEMENT_ASSESSMENT_RELATIONSHIP_REMAINS_UNUSUAL_AFTER_SEMANTIC_CLEANUP_AND_EXISTING_EVIDENCE_RECHECK"
      },
      "decision":"DO_NOT_KILL_CASE" if not has_richer_causal else "INSPECT_EXISTING_PROPERTY_CAUSAL_EVIDENCE_NEXT",
      "single_next_fact":"AUTHORITATIVE_CURRENT_IMPROVEMENT_CHARACTERISTICS_OR_ASSESSMENT_RECORD_DETAIL_THAT_EXPLAINS_THE_ALLOCATION" if not has_richer_causal else "INSPECT_ADDITIONAL_EXISTING_PROPERTY_CAUSAL_EVIDENCE",
      "policy":{"one_property_first":True,"existing_evidence_first":True,"missing_information_nonblocking":True,"data_quality_is_not_opportunity_evidence":True,"title_activity_not_causal_property_evidence":True,"seller_intent_inferred":False,"marketing_execution":False},
      "database_writes":0,
      "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"IF_NO_EXISTING_CAUSAL_PROPERTY_EVIDENCE_EXISTS, AUTHORIZE_ONE_EXTERNAL_AUTHORITATIVE_PROPERTY_OR_ASSESSMENT_LOOKUP_FOR_THIS_SINGLE_PARCEL_BEFORE_SCALING"
    }
