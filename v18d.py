#!/usr/bin/env python3
"""V18D — Pattern Intersection + Recent Change Context.
Read-only explainable research-attention candidates, not seller ranking.
"""
import json, os
from collections import Counter, defaultdict
from datetime import date, datetime
import psycopg

VERSION="V18D"
SPECIAL={"ADM","EXD","FCD","PRB","QCD","WRD","CTC","CTF","ADD"}

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")
def _payload(v):
    try:return json.loads(v) if v else {}
    except:return {}
def _first(p,*ks):
    for k in ks:
        v=p.get(k)
        if v not in (None,""):return v
    return None
def _day(v):
    try:return datetime.strptime(str(v).strip()[:10],"%Y-%m-%d").date() if v else None
    except:return None
def _pct(vals,x):
    return 100*sum(v<=x for v in vals)/len(vals) if vals and x is not None else None

def build_v18d():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,event_date,payload_json,first_seen_at,last_seen_at
                       FROM evidence_ledger WHERE is_current=1 ORDER BY parcel_id""")
        rows=cur.fetchall()
        cur.execute("SELECT parcel_id,state FROM investigation_state")
        states=dict(cur.fetchall())

    by=defaultdict(list)
    for r in rows:by[r[0]].append(r)
    today=date.today(); raw=[]; code_props=Counter()
    for parcel,evs in by.items():
        tr=[r for r in evs if r[1]=="TRANSFER_TITLE"]; dates=[]; codes=Counter()
        for r in tr:
            p=_payload(r[3]); d=_day(r[2]) or _day(_first(p,"RECORDDATE","recorddate","record_date"))
            if d:dates.append(d)
            c=_first(p,"DOCCODE","doccode","doc_code","document_code")
            if c:codes[str(c)]+=1
        for c in codes:code_props[c]+=1
        raw.append({"parcel_id":parcel,"ev":len(evs),"own":sum(r[1]=="OWNERSHIP" for r in evs),
                    "tr":len(tr),"dd":len(set(dates)),"latest":max(dates) if dates else None,"codes":codes})
    n=len(raw)
    trs=[p["tr"] for p in raw]; dds=[p["dd"] for p in raw]; owns=[p["own"] for p in raw]
    yrs=[(today-p["latest"]).days/365.2425 for p in raw if p["latest"]]

    candidates=[]; reason_counts=Counter()
    for p in raw:
        y=(today-p["latest"]).days/365.2425 if p["latest"] else None
        patterns=[]
        if _pct(trs,p["tr"])>=95 and _pct(dds,p["dd"])>=90:patterns.append("HIGH_TRANSFER_ACTIVITY_DEPTH")
        if y is not None and _pct(yrs,y)>=95 and p["tr"]<=3:patterns.append("LONG_QUIET_TRANSFER_HISTORY")
        if y is not None and _pct(yrs,y)<=5 and p["tr"]>=5:patterns.append("RECENT_ACTIVITY_ON_DEEPER_HISTORY")
        rare=[c for c in p["codes"] if code_props[c] <= max(5,round(n*.005))]
        if rare:patterns.append("RARE_DOCUMENT_CODE_PRESENT")
        if _pct(owns,p["own"])>=99 and p["own"]>=3:patterns.append("HIGH_OWNERSHIP_RECORD_DEPTH")
        if p["tr"]==0:patterns.append("NO_TRANSFER_TITLE_MEMORY")

        recent = y is not None and y <= 1.0
        special=sorted(c for c in p["codes"] if c in SPECIAL)
        reasons=[]
        if len(patterns)>=2:
            reasons.append("MULTIPLE_FACTUAL_PATTERNS_INTERSECT")
        if recent and len(patterns)>=1:
            reasons.append("PATTERN_PLUS_TRANSFER_WITHIN_ONE_YEAR")
        if recent and special:
            reasons.append("RECENT_TRANSFER_CONTEXT_INCLUDES_NON_BSD_DOCUMENT_TYPE")
        if "RARE_DOCUMENT_CODE_PRESENT" in patterns and len(patterns)>=2:
            reasons.append("RARE_DOCUMENT_CONTEXT_INTERSECTS_ANOTHER_PATTERN")

        if reasons:
            for r in reasons:reason_counts[r]+=1
            questions=[]
            if "MULTIPLE_FACTUAL_PATTERNS_INTERSECT" in reasons:
                questions.append("Do the intersecting factual patterns belong to one coherent chronology or unrelated historical events?")
            if recent:
                questions.append("What is the exact authoritative sequence and document context surrounding the recent transfer activity?")
            if special:
                questions.append("How do the non-BSD document types fit chronologically with the property's conveyance history?")
            if rare:
                questions.append("What does the authoritative source establish about the rare document event, without inferring motive?")
            candidates.append({
              "parcel_id":p["parcel_id"],"current_investigation_state":states.get(p["parcel_id"]),
              "patterns":patterns,"research_attention_reasons":reasons,
              "factual_context":{"transfer_rows":p["tr"],"distinct_transfer_dates":p["dd"],
                "ownership_rows":p["own"],"latest_transfer_date":p["latest"].isoformat() if p["latest"] else None,
                "years_since_latest_transfer":round(y,2) if y is not None else None,
                "document_codes":dict(sorted(p["codes"].items())),"rare_codes":rare,
                "non_bsd_context_codes":special},
              "next_factual_questions":questions,
              "boundary":"Research attention only; not seller intent, motivation, distress, outreach priority, or INVESTIGATE promotion."
            })

    candidates.sort(key=lambda x:(-len(x["research_attention_reasons"]),-len(x["patterns"]),x["parcel_id"]))
    return {"status":"ok","version":VERSION,"mode":"PATTERN_INTERSECTION_RECENT_CHANGE_CONTEXT_READ_ONLY",
      "summary":{"properties_evaluated":n,"research_attention_candidates":len(candidates),
        "multi_pattern_candidates":sum(len(x["patterns"])>=2 for x in candidates),
        "recent_with_pattern_candidates":sum("PATTERN_PLUS_TRANSFER_WITHIN_ONE_YEAR" in x["research_attention_reasons"] for x in candidates),
        "reason_counts":dict(sorted(reason_counts.items())),
        "already_investigate_among_candidates":sum(x["current_investigation_state"]=="INVESTIGATE" for x in candidates),
        "evidence_rows_consumed":len(rows)},
      "candidates":candidates[:75],
      "decision_boundary":{"research_attention_explained":True,"overall_rank_created":False,
        "seller_score_created":False,"seller_intent_inferred":False,"database_writes":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"ROUTE_EXPLAINABLE_CANDIDATES_TO_TARGETED_FACTUAL_RESEARCH_QUESTIONS"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
