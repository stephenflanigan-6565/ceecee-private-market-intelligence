#!/usr/bin/env python3
"""V18F — Unresolved Factual Question Research Router.
Read-only. Routes only PARTIAL/UNRESOLVED memory questions by missing evidence.
"""
import json, os
from collections import Counter, defaultdict
from datetime import date, datetime
import psycopg

VERSION="V18F"
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

def build_v18f():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,evidence_type,source,source_record_id,event_date,
                              evidence_grade,quality_state,payload_json
                       FROM evidence_ledger WHERE is_current=1 ORDER BY parcel_id,event_date NULLS FIRST""")
        rows=cur.fetchall()

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

    jobs=[]; route_counts=Counter(); status_counts=Counter(); properties=set()
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
        if not reasons:continue

        transfers=[]
        for r in p["evs"]:
            if r[1]!="TRANSFER_TITLE":continue
            q=_payload(r[8])
            transfers.append({"source_record_id":str(r[4]) if r[4] is not None else None,
              "doccode":_first(q,"DOCCODE","doccode","doc_code","document_code"),
              "recorddate":str(_first(q,"RECORDDATE","recorddate","record_date"))[:10] if _first(q,"RECORDDATE","recorddate","record_date") else None,
              "event_date":str(r[5])[:10] if r[5] else None,
              "liberpage":_first(q,"LIBERPAGE","liberpage","liber_page"),"quality_state":r[7]})

        def add(question,status,route,missing,ids,why):
            status_counts[status]+=1; route_counts[route]+=1; properties.add(p["parcel_id"])
            jobs.append({"parcel_id":p["parcel_id"],"question":question,"memory_status":status,
              "research_route":route,"missing_evidence":missing,
              "target_source_record_ids":sorted(set(x for x in ids if x)),
              "routing_basis":why,"patterns":patterns})

        if len(patterns)>=2:
            add("Do the intersecting factual patterns belong to one coherent chronology or unrelated historical events?",
                "PARTIAL","CHRONOLOGY_RELATIONSHIP_ANALYSIS",
                ["EVENT_RELATIONSHIP_CONTEXT"],[x["source_record_id"] for x in transfers],
                "Memory can assemble event chronology but row co-occurrence alone does not establish factual relationship among events.")

        if recent and patterns:
            rr=[x for x in transfers if x["recorddate"] and _day(x["recorddate"]) and (today-_day(x["recorddate"])).days<=366]
            complete=[x for x in rr if x["doccode"] and x["recorddate"] and x["liberpage"]]
            if not rr:
                add("What is the exact authoritative sequence and document context surrounding the recent transfer activity?",
                    "UNRESOLVED","TARGETED_AUTHORITATIVE_GIS_RECHECK",
                    ["RECENT_RECORDING_IDENTITY_OR_RECORDDATE","LIBERPAGE"],[x["source_record_id"] for x in transfers if x["doccode"]],
                    "Pattern logic indicates recent activity, but current memory has no completed recent RECORDDATE row.")
            elif len(complete)!=len(rr):
                ids=[x["source_record_id"] for x in rr if not (x["doccode"] and x["recorddate"] and x["liberpage"])]
                add("What is the exact authoritative sequence and document context surrounding the recent transfer activity?",
                    "PARTIAL","TARGETED_AUTHORITATIVE_GIS_RECHECK",
                    ["RECORDDATE_OR_LIBERPAGE_COMPLETION"],ids,
                    "Recent event exists in memory but authoritative recording metadata is incomplete.")

        if special:
            sr=[x for x in transfers if x["doccode"] in special]
            incomplete=[x for x in sr if not (x["recorddate"] and x["liberpage"])]
            if incomplete:
                add("How do the non-BSD document types fit chronologically with the property's conveyance history?",
                    "PARTIAL","TARGETED_AUTHORITATIVE_GIS_RECHECK",
                    ["RECORDDATE","LIBERPAGE"],[x["source_record_id"] for x in incomplete],
                    "One or more relevant non-BSD events lack recording date and/or liber/page needed for exact chronology placement.")

        if rare:
            rr=[x for x in transfers if x["doccode"] in rare]
            incomplete=[x for x in rr if not (x["recorddate"] and x["liberpage"])]
            if incomplete:
                add("What does the authoritative source establish about the rare document event, without inferring motive?",
                    "PARTIAL","TARGETED_AUTHORITATIVE_GIS_RECHECK",
                    ["RECORDDATE","LIBERPAGE"],[x["source_record_id"] for x in incomplete],
                    "Rare-code event is known but authoritative recording metadata is incomplete.")

    return {"status":"ok","version":VERSION,"mode":"PARTIAL_UNRESOLVED_FACTUAL_RESEARCH_ROUTER_READ_ONLY",
      "summary":{"properties_routed":len(properties),"research_jobs":len(jobs),
        "memory_status_counts":dict(status_counts),"route_counts":dict(route_counts),
        "evidence_rows_consumed":len(rows)},
      "research_jobs":jobs,
      "decision_boundary":{"answered_questions_excluded":True,"external_research_performed":False,
        "database_writes":False,"seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"EXECUTE_ONLY_TARGETED_AUTHORITATIVE_GIS_RECHECK_JOBS_AND_RESOLVE_CHRONOLOGY_FROM_EXISTING_MEMORY"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
