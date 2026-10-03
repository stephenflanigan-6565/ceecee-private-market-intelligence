#!/usr/bin/env python3
"""V18E — Candidate Question Resolution From Existing Memory.
Read-only. Resolves factual research questions from persistent evidence before new retrieval.
"""
import json, os
from collections import Counter, defaultdict
from datetime import date, datetime
import psycopg

VERSION="V18E"
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

def build_v18e():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,evidence_type,source,source_record_id,event_date,
                              evidence_grade,quality_state,payload_json
                       FROM evidence_ledger WHERE is_current=1 ORDER BY parcel_id,event_date NULLS FIRST""")
        rows=cur.fetchall()
        cur.execute("SELECT parcel_id,state FROM investigation_state")
        states=dict(cur.fetchall())

    by=defaultdict(list)
    for r in rows:by[r[0]].append(r)
    today=date.today(); raw=[]; code_props=Counter()

    for parcel,evs in by.items():
        tr=[r for r in evs if r[1]=="TRANSFER_TITLE"]; dates=[]; codes=Counter()
        for r in tr:
            p=_payload(r[8]); d=_day(r[5]) or _day(_first(p,"RECORDDATE","recorddate","record_date"))
            if d:dates.append(d)
            c=_first(p,"DOCCODE","doccode","doc_code","document_code")
            if c:codes[str(c)]+=1
        for c in codes:code_props[c]+=1
        raw.append({"parcel_id":parcel,"evs":evs,"own":sum(r[1]=="OWNERSHIP" for r in evs),
                    "tr":len(tr),"dd":len(set(dates)),"latest":max(dates) if dates else None,"codes":codes})
    n=len(raw); trs=[p["tr"] for p in raw]; dds=[p["dd"] for p in raw]; owns=[p["own"] for p in raw]
    yrs=[(today-p["latest"]).days/365.2425 for p in raw if p["latest"]]

    candidates=[]
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
        recent=y is not None and y<=1.0
        special=sorted(c for c in p["codes"] if c in SPECIAL)
        reasons=[]
        if len(patterns)>=2:reasons.append("MULTIPLE_FACTUAL_PATTERNS_INTERSECT")
        if recent and patterns:reasons.append("PATTERN_PLUS_TRANSFER_WITHIN_ONE_YEAR")
        if recent and special:reasons.append("RECENT_TRANSFER_CONTEXT_INCLUDES_NON_BSD_DOCUMENT_TYPE")
        if "RARE_DOCUMENT_CODE_PRESENT" in patterns and len(patterns)>=2:reasons.append("RARE_DOCUMENT_CONTEXT_INTERSECTS_ANOTHER_PATTERN")
        if reasons:candidates.append((p,patterns,rare,special,reasons))

    results=[]; status_counts=Counter(); question_count=0
    for p,patterns,rare,special,reasons in candidates:
        transfers=[]
        for r in p["evs"]:
            if r[1]!="TRANSFER_TITLE":continue
            q=_payload(r[8])
            transfers.append({
              "source_record_id":r[4],
              "event_date":str(r[5])[:10] if r[5] else None,
              "doccode":_first(q,"DOCCODE","doccode","doc_code","document_code"),
              "recorddate":str(_first(q,"RECORDDATE","recorddate","record_date"))[:10] if _first(q,"RECORDDATE","recorddate","record_date") else None,
              "docdate":str(_first(q,"DOCDATE","docdate","doc_date"))[:10] if _first(q,"DOCDATE","docdate","doc_date") else None,
              "liberpage":_first(q,"LIBERPAGE","liberpage","liber_page"),
              "source":r[3],"quality_state":r[7]
            })
        transfers.sort(key=lambda x:((x["recorddate"] or x["event_date"] or "0000"),str(x["source_record_id"])))

        qs=[]
        if "MULTIPLE_FACTUAL_PATTERNS_INTERSECT" in reasons:
            # Memory can establish chronology membership, but not always whether historical events are substantively related.
            qs.append({"question":"Do the intersecting factual patterns belong to one coherent chronology or unrelated historical events?",
              "status":"PARTIAL",
              "memory_answer":f"Persistent memory contains {len(transfers)} transfer/title rows and {p['own']} ownership rows for the same parcel; chronology can be assembled, but factual relatedness between events is not established by row co-occurrence alone.",
              "evidence_rows_used":len(transfers)+p["own"]})
        if "PATTERN_PLUS_TRANSFER_WITHIN_ONE_YEAR" in reasons:
            recent_rows=[x for x in transfers if x["recorddate"] and _day(x["recorddate"]) and (today-_day(x["recorddate"])).days<=366]
            complete=[x for x in recent_rows if x["doccode"] and x["recorddate"] and x["liberpage"]]
            st="ANSWERED" if recent_rows and len(complete)==len(recent_rows) else ("PARTIAL" if recent_rows else "UNRESOLVED")
            qs.append({"question":"What is the exact authoritative sequence and document context surrounding the recent transfer activity?",
              "status":st,
              "memory_answer":f"Memory contains {len(recent_rows)} transfer/title row(s) recorded within one year; {len(complete)} have DOCCODE + RECORDDATE + LIBERPAGE complete.",
              "recent_rows":recent_rows[:12]})
        if special:
            rows_special=[x for x in transfers if x["doccode"] in special]
            complete=[x for x in rows_special if x["recorddate"] and x["liberpage"]]
            st="ANSWERED" if rows_special and len(complete)==len(rows_special) else ("PARTIAL" if rows_special else "UNRESOLVED")
            qs.append({"question":"How do the non-BSD document types fit chronologically with the property's conveyance history?",
              "status":st,
              "memory_answer":f"Memory contains {len(rows_special)} relevant non-BSD row(s); {len(complete)} have recording date and liber/page sufficient for authoritative chronology placement.",
              "relevant_rows":rows_special[:12]})
        if rare:
            rr=[x for x in transfers if x["doccode"] in rare]
            complete=[x for x in rr if x["recorddate"] and x["liberpage"]]
            st="ANSWERED" if rr and len(complete)==len(rr) else ("PARTIAL" if rr else "UNRESOLVED")
            qs.append({"question":"What does the authoritative source establish about the rare document event, without inferring motive?",
              "status":st,
              "memory_answer":f"Memory contains {len(rr)} rare-code event row(s); {len(complete)} have recording date and liber/page. Memory establishes recorded event facts only, not motive.",
              "relevant_rows":rr[:12]})
        for q in qs:status_counts[q["status"]]+=1
        question_count+=len(qs)
        results.append({"parcel_id":p["parcel_id"],"current_investigation_state":states.get(p["parcel_id"]),
          "patterns":patterns,"research_attention_reasons":reasons,"questions":qs,
          "question_status_counts":dict(Counter(q["status"] for q in qs))})

    unresolved_properties=sum(any(q["status"]!="ANSWERED" for q in r["questions"]) for r in results)
    fully_answered=sum(r["questions"] and all(q["status"]=="ANSWERED" for q in r["questions"]) for r in results)
    return {"status":"ok","version":VERSION,"mode":"CANDIDATE_QUESTION_MEMORY_RESOLUTION_READ_ONLY",
      "summary":{"candidate_properties":len(results),"questions_evaluated":question_count,
        "question_status_counts":dict(status_counts),"fully_answered_properties":fully_answered,
        "properties_with_partial_or_unresolved_questions":unresolved_properties,
        "evidence_rows_consumed":len(rows)},
      "candidate_resolutions":results[:113],
      "decision_boundary":{"memory_first_resolution":True,"new_external_research_performed":False,
        "database_writes":False,"seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"ROUTE_ONLY_PARTIAL_AND_UNRESOLVED_FACTUAL_QUESTIONS_TO_TARGETED_RESEARCH"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
