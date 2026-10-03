#!/usr/bin/env python3
"""V18C — Explainable Factual Pattern / Anomaly Detection.
Read-only. Detects unusual factual combinations; creates no seller score/rank.
"""
import json, os
from collections import Counter, defaultdict
from datetime import date, datetime
import psycopg

VERSION="V18C"

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
    if v is None:return None
    try:return datetime.strptime(str(v).strip()[:10],"%Y-%m-%d").date()
    except Exception:return None

def _percentile(vals,x):
    if x is None or not vals:return None
    return 100.0*sum(v<=x for v in vals)/len(vals)

def build_v18c():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,event_date,payload_json
                       FROM evidence_ledger WHERE is_current=1 ORDER BY parcel_id""")
        rows=cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='BASELINE'")
        baseline=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='INVESTIGATE'")
        investigate=cur.fetchone()[0]

    by=defaultdict(list)
    for r in rows: by[r[0]].append(r)
    today=date.today()
    raw=[]
    code_prop=Counter()
    for parcel,evs in by.items():
        own=sum(r[1]=="OWNERSHIP" for r in evs)
        tr=[r for r in evs if r[1]=="TRANSFER_TITLE"]
        dates=[]; codes=Counter()
        for r in tr:
            p=_payload(r[3])
            d=_day(r[2]) or _day(_first(p,"RECORDDATE","recorddate","record_date"))
            if d:dates.append(d)
            c=_first(p,"DOCCODE","doccode","doc_code","document_code")
            if c:codes[str(c)]+=1
        for c in codes:code_prop[c]+=1
        raw.append({"parcel_id":parcel,"evidence_rows":len(evs),"ownership_rows":own,
                    "transfer_rows":len(tr),"distinct_dates":len(set(dates)),
                    "first":min(dates) if dates else None,"latest":max(dates) if dates else None,
                    "codes":codes})
    n=len(raw)
    arrays={
      "evidence_rows":[p["evidence_rows"] for p in raw],
      "ownership_rows":[p["ownership_rows"] for p in raw],
      "transfer_rows":[p["transfer_rows"] for p in raw],
      "distinct_dates":[p["distinct_dates"] for p in raw],
      "years_since_latest":[(today-p["latest"]).days/365.2425 for p in raw if p["latest"]]
    }

    findings=[]
    pattern_counts=Counter()
    for p in raw:
        yrs=(today-p["latest"]).days/365.2425 if p["latest"] else None
        tp=_percentile(arrays["transfer_rows"],p["transfer_rows"])
        dp=_percentile(arrays["distinct_dates"],p["distinct_dates"])
        op=_percentile(arrays["ownership_rows"],p["ownership_rows"])
        rp=_percentile(arrays["years_since_latest"],yrs) if yrs is not None else None
        patterns=[]

        # Each pattern is a factual combination with an explicit population-relative basis.
        if tp is not None and tp>=95 and dp is not None and dp>=90:
            patterns.append({"pattern":"HIGH_TRANSFER_ACTIVITY_DEPTH",
              "why":f"{p['transfer_rows']} transfer rows and {p['distinct_dates']} distinct recorded dates are both near the upper tail of the 2,082-property universe."})
        if rp is not None and rp>=95 and p["transfer_rows"]<=3:
            patterns.append({"pattern":"LONG_QUIET_TRANSFER_HISTORY",
              "why":f"Latest recorded transfer is about {yrs:.1f} years ago while the property has only {p['transfer_rows']} transfer rows in memory."})
        if rp is not None and rp<=5 and p["transfer_rows"]>=5:
            patterns.append({"pattern":"RECENT_ACTIVITY_ON_DEEPER_HISTORY",
              "why":f"Latest recorded transfer is about {yrs:.2f} years ago on a history containing {p['transfer_rows']} transfer rows."})
        rare=[c for c in p["codes"] if code_prop[c] <= max(5, round(n*.005))]
        if rare:
            patterns.append({"pattern":"RARE_DOCUMENT_CODE_PRESENT",
              "why":"Contains document code(s) appearing on no more than about 0.5% of properties: "+", ".join(sorted(rare)),
              "codes":sorted(rare)})
        if op is not None and op>=99 and p["ownership_rows"]>=3:
            patterns.append({"pattern":"HIGH_OWNERSHIP_RECORD_DEPTH",
              "why":f"{p['ownership_rows']} ownership rows are in the extreme upper tail of the universe."})
        if p["transfer_rows"]==0:
            patterns.append({"pattern":"NO_TRANSFER_TITLE_MEMORY",
              "why":"Property has no TRANSFER_TITLE evidence in current persistent memory."})

        if patterns:
            for x in patterns:pattern_counts[x["pattern"]]+=1
            findings.append({
              "parcel_id":p["parcel_id"],
              "factual_dimensions":{"evidence_rows":p["evidence_rows"],"ownership_rows":p["ownership_rows"],
                "transfer_rows":p["transfer_rows"],"transfer_distinct_dates":p["distinct_dates"],
                "latest_transfer_date":p["latest"].isoformat() if p["latest"] else None,
                "years_since_latest_transfer":round(yrs,2) if yrs is not None else None,
                "document_codes":dict(sorted(p["codes"].items()))},
              "patterns":patterns,
              "interpretation_boundary":"Unusual factual context only. Does not establish seller intent, motivation, distress, or contact priority."
            })

    multi=sum(len(f["patterns"])>=2 for f in findings)
    return {"status":"ok","version":VERSION,"mode":"EXPLAINABLE_FACTUAL_PATTERN_ANOMALY_DETECTION_READ_ONLY",
      "summary":{"properties_evaluated":n,"evidence_rows_consumed":len(rows),
        "properties_with_one_or_more_factual_patterns":len(findings),
        "properties_with_multiple_patterns":multi,
        "pattern_counts":dict(sorted(pattern_counts.items())),
        "baseline_state_count":baseline,"investigate_state_count":investigate},
      "pattern_definitions":{
        "HIGH_TRANSFER_ACTIVITY_DEPTH":"Upper-tail transfer row count combined with upper-tail distinct transfer dates.",
        "LONG_QUIET_TRANSFER_HISTORY":"Upper-tail time since latest transfer combined with shallow transfer memory.",
        "RECENT_ACTIVITY_ON_DEEPER_HISTORY":"Very recent recorded transfer on a multi-event transfer history.",
        "RARE_DOCUMENT_CODE_PRESENT":"At least one document code appears on <= about 0.5% of properties.",
        "HIGH_OWNERSHIP_RECORD_DEPTH":"Extreme upper-tail ownership evidence depth.",
        "NO_TRANSFER_TITLE_MEMORY":"No transfer/title evidence exists in current memory."
      },
      "examples":findings[:40],
      "decision_boundary":{"pattern_detection":True,"overall_rank_created":False,
        "seller_score_created":False,"seller_intent_inferred":False,"database_writes":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"TEST_PATTERN_INTERSECTIONS_AND_RECENT_CHANGE_CONTEXT_FOR_EXPLAINABLE_RESEARCH_PRIORITY"},
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}}
