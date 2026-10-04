#!/usr/bin/env python3
import os, json, math, statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone

VERSION = "PROPERTY_ANOMALY_LAB_V1"
MARKET = "WESTHAMPTON_BEACH_NY"
FAMILIES = ("PROPERTY_CONTEXT", "ASSESSMENT_CONTEXT")

ALIASES = {
    "address": ["property_address","address","fulladdress","full_address","site_address","situs_address"],
    "property_class": ["property_class","class","propertyclass","landuse","land_use","use_class","property_type"],
    "acres": ["acres","acreage","lot_acres","parcel_acres"],
    "assessment_total": ["assessment_total","total_assessment","assessed_total","total_assessed_value","assessed_value"],
    "assessment_market_value": ["assessment_market_value","market_value","estimated_market_value","full_market_value"],
    "land_assessment": ["land_assessment","assessed_land","land_assessed_value"],
    "improvement_assessment": ["improvement_assessment","assessed_improvement","improvement_assessed_value","building_assessment"],
}

def _payload(v):
    if isinstance(v, dict): return v
    if not v: return {}
    try:
        x=json.loads(v)
        return x if isinstance(x,dict) else {}
    except Exception: return {}

def _flat(d, prefix=""):
    out={}
    for k,v in d.items():
        key=(prefix+str(k)).lower().strip()
        if isinstance(v,dict): out.update(_flat(v,key+"."))
        else: out[key]=v
    return out

def _num(v):
    if v is None or isinstance(v,bool): return None
    try:
        s=str(v).strip().replace(",","").replace("$","")
        if not s: return None
        x=float(s)
        return x if math.isfinite(x) else None
    except Exception: return None

def _pick(flat, aliases):
    for a in aliases:
        a=a.lower()
        if a in flat and flat[a] not in (None,""): return flat[a]
    # nested payloads: permit exact terminal key match, not fuzzy substring guessing
    for a in aliases:
        a=a.lower()
        hits=[v for k,v in flat.items() if k.split(".")[-1]==a and v not in (None,"")]
        if hits: return hits[0]
    return None

def _median(xs): return statistics.median(xs) if xs else None

def _pct_rank(sorted_x, x):
    if not sorted_x or x is None: return None
    below=sum(1 for v in sorted_x if v < x); equal=sum(1 for v in sorted_x if v == x)
    return (below + 0.5*equal)/len(sorted_x)

def _mad(xs):
    if not xs: return None
    m=statistics.median(xs)
    return statistics.median([abs(x-m) for x in xs])

def _robust_z(x, xs):
    if x is None or len(xs)<5: return None
    med=_median(xs); mad=_mad(xs)
    if mad in (None,0): return None
    return 0.67448975*(x-med)/mad

def build_property_anomaly_lab_v1():
    import psycopg
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,evidence_family,source_record_id,event_date,quality_state,payload_json
                       FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1 AND evidence_family = ANY(%s)
                       ORDER BY parcel_id,evidence_family,evidence_key""",(MARKET,list(FAMILIES)))
        rows=cur.fetchall()
        cur.execute("""SELECT COUNT(DISTINCT parcel_id) FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1""",(MARKET,))
        universe=int(cur.fetchone()[0])
    finally:
        conn.close()

    key_stats={f:Counter() for f in FAMILIES}; fam_parcels={f:set() for f in FAMILIES}
    by=defaultdict(dict); provenance=defaultdict(list)
    for pid,fam,sid,ed,qs,pj in rows:
        p=_payload(pj); flat=_flat(p)
        fam_parcels[fam].add(pid)
        for k,v in flat.items():
            if v not in (None,""): key_stats[fam][k]+=1
        # if duplicate current rows exist, merge non-empty keys without destroying prior facts
        by[pid].setdefault(fam,{})
        for k,v in flat.items():
            if v not in (None,"") and k not in by[pid][fam]: by[pid][fam][k]=v
        provenance[pid].append({"family":fam,"source_record_id":sid,"event_date":str(ed) if ed else None,"quality_state":qs})

    records=[]; coverage=Counter()
    for pid,fams in by.items():
        merged={}
        for fam in FAMILIES: merged.update(fams.get(fam,{}))
        rec={"parcel_id":pid}
        for logical,aliases in ALIASES.items():
            raw=_pick(merged,aliases)
            rec[logical]=_num(raw) if logical in {"acres","assessment_total","assessment_market_value","land_assessment","improvement_assessment"} else (str(raw).strip() if raw not in (None,"") else None)
            if rec[logical] is not None: coverage[logical]+=1
        if rec["acres"] is not None and rec["acres"]<=0: rec["acres"]=None
        records.append(rec)

    # v1 peers: same property class across WHB. Do not fabricate micro-geography until a verified geography field exists.
    groups=defaultdict(list)
    for r in records:
        if r["property_class"]: groups[r["property_class"]].append(r)

    candidates=[]; anomaly_counts=Counter(); supported=[]
    can_acre_assess=coverage["acres"]>=20 and (coverage["assessment_total"]>=20 or coverage["assessment_market_value"]>=20)
    can_land_impr=coverage["land_assessment"]>=20 and coverage["improvement_assessment"]>=20
    if can_acre_assess: supported += ["A1_ASSESSMENT_PER_ACRE_OUTLIER","A2_PARCEL_SIZE_VALUE_MISMATCH","A3_CLASS_PEER_ECONOMIC_MISMATCH"]
    if can_land_impr: supported += ["A4_LAND_IMPROVEMENT_ASSESSMENT_MISMATCH"]

    for r in records:
        cls=r["property_class"]
        peers=groups.get(cls,[]) if cls else []
        if len(peers)<20: continue
        facts=[]; flags=[]
        acre_vals=sorted([p["acres"] for p in peers if p["acres"] is not None])
        val_field="assessment_market_value" if sum(p["assessment_market_value"] is not None for p in peers)>=20 else "assessment_total"
        vals=sorted([p[val_field] for p in peers if p[val_field] is not None])
        per_acre=[p[val_field]/p["acres"] for p in peers if p[val_field] is not None and p["acres"] not in (None,0)]
        if can_acre_assess and r["acres"] is not None and r[val_field] is not None and len(per_acre)>=20:
            pa=r[val_field]/r["acres"]
            z=_robust_z(pa,per_acre); apr=_pct_rank(acre_vals,r["acres"]); vpr=_pct_rank(vals,r[val_field])
            if z is not None and abs(z)>=3.5:
                flags.append("A1_ASSESSMENT_PER_ACRE_OUTLIER"); anomaly_counts[flags[-1]]+=1
                facts.append({"metric":"value_per_acre","value":round(pa,2),"peer_median":round(_median(per_acre),2),"robust_z":round(z,2)})
            if apr is not None and vpr is not None and abs(apr-vpr)>=0.60:
                flags.append("A2_PARCEL_SIZE_VALUE_MISMATCH"); anomaly_counts[flags[-1]]+=1
                facts.append({"metric":"acreage_vs_value_percentile","acreage_percentile":round(apr,3),"value_percentile":round(vpr,3),"gap":round(apr-vpr,3)})
            zv=_robust_z(r[val_field],vals)
            if zv is not None and abs(zv)>=3.5:
                flags.append("A3_CLASS_PEER_ECONOMIC_MISMATCH"); anomaly_counts[flags[-1]]+=1
                facts.append({"metric":val_field,"value":round(r[val_field],2),"peer_median":round(_median(vals),2),"robust_z":round(zv,2)})
        if can_land_impr and r["land_assessment"] is not None and r["improvement_assessment"] is not None:
            ratios=[p["improvement_assessment"]/(p["land_assessment"] or 1) for p in peers if p["land_assessment"] not in (None,0) and p["improvement_assessment"] is not None]
            if len(ratios)>=20 and r["land_assessment"]>0:
                ratio=r["improvement_assessment"]/r["land_assessment"]; z=_robust_z(ratio,ratios)
                if z is not None and abs(z)>=3.5:
                    flags.append("A4_LAND_IMPROVEMENT_ASSESSMENT_MISMATCH"); anomaly_counts[flags[-1]]+=1
                    facts.append({"metric":"improvement_to_land_assessment_ratio","value":round(ratio,4),"peer_median":round(_median(ratios),4),"robust_z":round(z,2)})
        if len(set(flags))>=2: anomaly_counts["A5_MULTI_FACTOR_UNEXPLAINED_ANOMALY"]+=1
        if flags:
            candidates.append({"parcel_id":r["parcel_id"],"property_address":r["address"],"property_class":cls,
                "peer_definition":"WESTHAMPTON_BEACH + SAME_PROPERTY_CLASS","peer_count":len(peers),
                "anomaly_families":sorted(set(flags)),"observed_comparisons":facts,
                "hypothesis":"PROPERTY_OR_LAND_RELATIONSHIP_DESERVES_FACTUAL_RESEARCH",
                "seller_intent":"UNKNOWN","important_unknown":"WHY_THE_PROPERTY_DIFFERS_FROM_DEFENSIBLE_CLASS_PEERS",
                "next_research_question":"What verified property/site/use fact best explains this anomaly?",
                "research_state":"INVESTIGATE" if len(set(flags))>=2 else "WATCH"})

    # Transparent ordering for inspection only: multi-factor first, then number of flags, then parcel id. Not seller ranking.
    candidates.sort(key=lambda x:(-(1 if len(x["anomaly_families"])>=2 else 0),-len(x["anomaly_families"]),x["parcel_id"]))
    field_inventory={}
    for fam in FAMILIES:
        denom=max(1,len(fam_parcels[fam]))
        field_inventory[fam]={"properties":len(fam_parcels[fam]),"fields":[{"field":k,"non_null":n,"coverage_pct":round(100*n/denom,2)} for k,n in key_stats[fam].most_common()]}

    return {
      "status":"ok","version":VERSION,"mode":"READ_ONLY_PROPERTY_MARKET_ANOMALY_LAB",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "summary":{"properties_evaluated_full_universe":universe,"properties_with_target_evidence":len(records),"evidence_rows_consumed":len(rows),
                 "property_context_properties":len(fam_parcels["PROPERTY_CONTEXT"]),"assessment_context_properties":len(fam_parcels["ASSESSMENT_CONTEXT"]),
                 "supported_anomaly_families":supported,"candidate_properties":len(candidates),"anomaly_counts":dict(anomaly_counts)},
      "logical_field_coverage":dict(coverage),"field_inventory":field_inventory,
      "peer_policy":{"v1":"WESTHAMPTON_BEACH + SAME_PROPERTY_CLASS","minimum_peer_count":20,"note":"No micro-geography is inferred unless a verified location field is present in a later test."},
      "threshold_policy":{"robust_z_abs":3.5,"acreage_value_percentile_gap_abs":0.60,"purpose":"high-specificity research trigger; not seller probability"},
      "inspection_candidates":candidates[:25],
      "policy":{"seller_probability_created":False,"title_can_qualify":False,"missing_data_nonblocking":True,"candidate_is_research_hypothesis_only":True},
      "database_writes":0,
      "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"REVIEW_EXPLAINABILITY_AND_INFORMATION_VALUE_BEFORE_ANY_NEW_SOURCE_OR_PRODUCTION_STATE_CHANGE"
    }
