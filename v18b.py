#!/usr/bin/env python3
"""V18B — Cross-Property Factual Comparison Dimensions.
Read-only descriptive comparison across the residential universe.
No seller scoring, ranking, state promotion, or writes.
"""
import json, os, math
from collections import Counter, defaultdict
from datetime import date, datetime
import psycopg

VERSION="V18B"
FAMILIES=("PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE")

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _payload(v):
    try: return json.loads(v) if v else {}
    except Exception: return {}

def _first(p,*keys):
    for k in keys:
        v=p.get(k)
        if v not in (None,""): return v
    return None

def _day(v):
    if v is None: return None
    s=str(v).strip()[:10]
    try: return datetime.strptime(s,"%Y-%m-%d").date()
    except Exception: return None

def _pct(values, x):
    if x is None or not values: return None
    a=sorted(values)
    return round(100.0*sum(1 for v in a if v <= x)/len(a),1)

def _quantiles(values):
    if not values: return {}
    a=sorted(values)
    def q(p):
        i=(len(a)-1)*p
        lo=int(math.floor(i)); hi=int(math.ceil(i))
        if lo==hi: return a[lo]
        return round(a[lo]+(a[hi]-a[lo])*(i-lo),2)
    return {"min":a[0],"p25":q(.25),"median":q(.5),"p75":q(.75),"max":a[-1]}

def build_v18b():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,source_record_id,event_date,payload_json
                       FROM evidence_ledger WHERE is_current=1 ORDER BY parcel_id""")
        rows=cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='BASELINE'")
        baseline=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='INVESTIGATE'")
        investigate=cur.fetchone()[0]

    by=defaultdict(list)
    for r in rows: by[r[0]].append(r)

    raw=[]
    doc_profile_prevalence=Counter()
    today=date.today()
    for parcel, evs in by.items():
        fam=Counter(r[1] for r in evs)
        codes=Counter(); dates=[]
        for r in evs:
            if r[1]!="TRANSFER_TITLE": continue
            p=_payload(r[4])
            code=_first(p,"DOCCODE","doccode","doc_code","document_code")
            if code: codes[str(code)]+=1
            d=_day(r[3]) or _day(_first(p,"RECORDDATE","recorddate","record_date"))
            if d: dates.append(d)
        for c in codes: doc_profile_prevalence[c]+=1
        first=min(dates) if dates else None
        latest=max(dates) if dates else None
        raw.append({
          "parcel_id":parcel,
          "evidence_rows":len(evs),
          "ownership_rows":fam["OWNERSHIP"],
          "transfer_rows":fam["TRANSFER_TITLE"],
          "transfer_distinct_dates":len(set(dates)),
          "chronology_span_years":round((latest-first).days/365.2425,2) if first and latest else None,
          "years_since_latest_transfer":round((today-latest).days/365.2425,2) if latest else None,
          "first_transfer_date":first.isoformat() if first else None,
          "latest_transfer_date":latest.isoformat() if latest else None,
          "document_codes":dict(sorted(codes.items())),
          "families_missing":[f for f in FAMILIES if fam[f]==0]
        })

    metrics=["evidence_rows","ownership_rows","transfer_rows","transfer_distinct_dates",
             "chronology_span_years","years_since_latest_transfer"]
    arrays={m:[p[m] for p in raw if p[m] is not None] for m in metrics}
    distributions={m:_quantiles(arrays[m]) for m in metrics}

    profiles=[]
    for p in raw:
        comparisons={}
        for m in metrics:
            comparisons[m]={"value":p[m],"universe_percentile_at_or_below":_pct(arrays[m],p[m])}
        code_context={}
        for code,count in p["document_codes"].items():
            n=doc_profile_prevalence[code]
            code_context[code]={
              "property_event_count":count,
              "properties_with_code":n,
              "property_prevalence_pct":round(100*n/len(raw),1)
            }
        profiles.append({
          **p,
          "comparative_dimensions":comparisons,
          "document_code_universe_context":code_context,
          "comparison_note":"Descriptive factual context only; percentile is not a seller score or priority rank."
        })

    # Samples deliberately show dimensional extremes, not an overall ranking.
    samples={}
    for metric in ("transfer_rows","ownership_rows","chronology_span_years","years_since_latest_transfer"):
        valid=[p for p in profiles if p[metric] is not None]
        samples[metric]={
          "low_examples":sorted(valid,key=lambda x:(x[metric],x["parcel_id"]))[:3],
          "high_examples":sorted(valid,key=lambda x:(-x[metric],x["parcel_id"]))[:3]
        }

    return {
      "status":"ok","version":VERSION,"mode":"CROSS_PROPERTY_FACTUAL_COMPARISON_READ_ONLY",
      "summary":{
        "properties_compared":len(profiles),
        "evidence_rows_consumed":len(rows),
        "baseline_state_count":baseline,
        "investigate_state_count":investigate,
        "profiles_missing_transfer_title":sum(1 for p in profiles if "TRANSFER_TITLE" in p["families_missing"]),
        "distinct_document_codes":len(doc_profile_prevalence)
      },
      "universe_distributions":distributions,
      "document_code_prevalence":{
        c:{"properties":n,"prevalence_pct":round(100*n/len(profiles),1)}
        for c,n in sorted(doc_profile_prevalence.items(), key=lambda kv:(-kv[1],kv[0]))
      },
      "dimensional_examples":samples,
      "decision_boundary":{
        "cross_property_comparison":True,
        "overall_rank_created":False,
        "seller_score_created":False,
        "seller_intent_inferred":False,
        "database_writes":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"BUILD_EXPLAINABLE_FACTUAL_PATTERN_AND_ANOMALY_DETECTION_FROM_COMPARISON_DIMENSIONS"
      },
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "new_candidate_created":False,"contact_authorized":False,"outreach_touched":False}
    }
