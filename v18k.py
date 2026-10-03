#!/usr/bin/env python3
"""V18K — Governed Candidate Narrowing / Research Continuation.
Read-only. Uses factual evidence + locked V18D-style intersections.
Missing facts create a follow-up lane; they never exclude research.
No seller score, intent inference, ranking, outreach, promotion, or DB writes.
"""
import json, os
from collections import defaultdict, Counter
from datetime import datetime, timezone
import psycopg

VERSION="V18K"

# Proven unresolved factual remainder from V18G–V18I.
SOURCE_FOLLOWUP={
"0905003000100010000","0905003000100028000","0905006000100026000",
"0905006000200009000","0905007000200024000","0905015000200016000",
"0905015000300011000","0905008000100014002","0905008000200015002",
"0905009000100020000","0905009000100023000","0905009000200026002",
"0905017000300028000"
}
CHRONOLOGY_FOLLOWUP={"0905020000200030000"}
RESOLVED_ROUTING_NOTE={"0905010000300004000":
    "Prior source identity 1225700 was proven to belong to parcel 0905015000500023000; do not reuse it for this parcel."}

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _payload(s):
    try:return json.loads(s) if s else {}
    except:return {}

def _code(p):
    for k in ("DOCCODE","doccode","doc_code","document_code"):
        v=p.get(k)
        if v:return str(v).strip().upper()
    return None

def _date(p,event_date):
    # RECORDDATE first. Never ENTRYDATE.
    for k in ("RECORDDATE","recorddate","record_date"):
        v=p.get(k)
        if v:
            s=str(v)
            if len(s)>=10 and s[:4].isdigit(): return s[:10]
            try:
                n=float(s)
                if n>10_000_000_000:
                    return datetime.fromtimestamp(n/1000,tz=timezone.utc).date().isoformat()
            except: pass
    if event_date:
        s=str(event_date)
        if len(s)>=10 and s[:4].isdigit(): return s[:10]
        try:
            n=float(s)
            if n>10_000_000_000:
                return datetime.fromtimestamp(n/1000,tz=timezone.utc).date().isoformat()
        except: pass
    return None

def build_v18k():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,event_date,payload_json
                       FROM evidence_ledger WHERE is_current=1""")
        rows=cur.fetchall()
        cur.execute("""SELECT parcel_id,state,contact_authorized,seller_intent_inferred
                       FROM investigation_state""")
        state_rows=cur.fetchall()

    ev=defaultdict(list)
    for pid,fam,ed,pj in rows: ev[pid].append((fam,ed,_payload(pj)))
    states={r[0]:{"state":r[1],"contact_authorized":bool(r[2]),
                  "seller_intent_inferred":bool(r[3])} for r in state_rows}
    parcels=sorted(ev)

    # Factual profile measures used by the locked V18C/D line.
    profile={}
    transfer_depths=[]; ownership_depths=[]
    for pid in parcels:
        tr=[x for x in ev[pid] if x[0]=="TRANSFER_TITLE"]
        ow=[x for x in ev[pid] if x[0]=="OWNERSHIP"]
        dates=sorted(set(d for _,ed,p in tr if (d:=_date(p,ed))))
        codes=sorted(set(c for _,_,p in tr if (c:=_code(p))))
        profile[pid]={"transfer_rows":len(tr),"ownership_rows":len(ow),
                      "transfer_dates":dates,"codes":codes,
                      "latest":dates[-1] if dates else None}
        transfer_depths.append(len(tr)); ownership_depths.append(len(ow))

    # Locked V18C factual thresholds from the proven population results:
    # high transfer activity = 8+ transfer rows; high ownership depth = 3+ ownership rows.
    # These are descriptive pattern flags, not seller scores.
    RARE={"GRT","APD","IAC","PTD","RRD","SHD","SCO","TSC"}
    cutoff="2025-10-03"  # one-year factual context relative to this Oct 2026 checkpoint

    # Rebuild the V18D-style 113 research-attention lane from factual intersections only.
    attention=[]
    for pid in parcels:
        p=profile[pid]; reasons=[]
        high_transfer=p["transfer_rows"]>=8
        high_owner=p["ownership_rows"]>=3
        rare=sorted(set(p["codes"]) & RARE)
        recent=bool(p["latest"] and p["latest"]>=cutoff)
        non_bsd_recent=recent and any(c!="BSD" for c in p["codes"])
        pattern_count=sum([high_transfer,high_owner,bool(rare)])

        if pattern_count>=2:
            reasons.append("MULTIPLE_FACTUAL_PATTERNS_INTERSECT")
        if recent and (high_transfer or high_owner or bool(rare)):
            reasons.append("PATTERN_PLUS_TRANSFER_WITHIN_ONE_YEAR")
        if rare and (high_transfer or high_owner):
            reasons.append("RARE_DOCUMENT_CONTEXT_INTERSECTS_ANOTHER_PATTERN")
        if non_bsd_recent and (high_transfer or high_owner or bool(rare)):
            reasons.append("RECENT_TRANSFER_CONTEXT_INCLUDES_NON_BSD_DOCUMENT_TYPE")
        if not reasons: continue

        open_items=[]
        if pid in SOURCE_FOLLOWUP:
            open_items.append("AUTHORITATIVE_RECORDING_METADATA_FOLLOWUP")
        if pid in CHRONOLOGY_FOLLOWUP:
            open_items.append("CHRONOLOGY_RELATIONSHIP_FOLLOWUP")
        if pid in RESOLVED_ROUTING_NOTE:
            open_items.append("RESOLVED_ROUTING_CORRECTION_NOTE")

        lane=("RESEARCH_CONTINUE_WITH_FOLLOWUP_ATTACHED"
              if any(x.endswith("FOLLOWUP") for x in open_items)
              else "FACTUALLY_READY_FOR_DEEPER_INTERPRETATION")
        st=states.get(pid,{"state":"BASELINE","contact_authorized":False,
                           "seller_intent_inferred":False})
        attention.append({
          "parcel_id":pid,
          "research_lane":lane,
          "attention_reasons":reasons,
          "factual_context":{"transfer_rows":p["transfer_rows"],
             "ownership_rows":p["ownership_rows"],"latest_recorded_transfer_date":p["latest"],
             "document_codes":p["codes"],"rare_document_codes":rare},
          "open_factual_items":open_items,
          "routing_note":RESOLVED_ROUTING_NOTE.get(pid),
          "investigation_state":st["state"],
          "research_may_continue":True,
          "contact_authorized":False,
          "seller_intent_inferred":False
        })

    lane_counts=Counter(x["research_lane"] for x in attention)
    reason_counts=Counter(r for x in attention for r in x["attention_reasons"])
    return {
      "status":"ok","version":VERSION,
      "mode":"GOVERNED_FACTUAL_CANDIDATE_NARROWING_READ_ONLY",
      "summary":{"properties_evaluated":len(parcels),"evidence_rows_consumed":len(rows),
        "research_attention_candidates":len(attention),
        "lane_counts":dict(lane_counts),"reason_counts":dict(reason_counts),
        "followup_does_not_stop_research":True,"database_writes":0},
      "research_lanes":{
        "FACTUALLY_READY_FOR_DEEPER_INTERPRETATION":
          "Current memory is sufficient for the next factual interpretation step.",
        "RESEARCH_CONTINUE_WITH_FOLLOWUP_ATTACHED":
          "Property remains fully researchable; unresolved factual items stay attached for later verification."
      },
      "candidates":attention,
      "decision_boundary":{"missing_data_is_not_exclusion":True,
        "research_continues_with_followup":True,"database_writes":False,
        "seller_score_created":False,"seller_intent_inferred":False,
        "overall_ranking_created":False,"investigate_promotion_authorized":False,
        "contact_authorized":False,
        "next_step_if_clean":"DEEPEN_FACTUAL_INTERPRETATION_OF_THE_RESEARCH_ATTENTION_LANE_WHILE_PRESERVING_FOLLOWUP_CATEGORIES"},
      "guards":{"database_writes":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}}
