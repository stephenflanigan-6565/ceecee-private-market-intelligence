#!/usr/bin/env python3
"""V18J — Factual Readiness + Investigation Relevance Layer.
Read-only. Missing data is an explicit state, never an exclusion from research.
No seller scoring, intent inference, outreach authorization, promotion, or DB writes.
"""
import json, os
from collections import defaultdict
from datetime import datetime, timezone
import psycopg

VERSION="V18J"

# Known open factual remainder established by V18G/H1/I.
SOURCE_INCOMPLETE_PARCELS={
"0905003000100010000","0905003000100028000","0905006000100026000",
"0905006000200009000","0905007000200024000","0905015000200016000",
"0905015000300011000","0905008000100014002","0905008000200015002",
"0905009000100020000","0905009000100023000","0905009000200026002",
"0905017000300028000"
}
# V18H1 had 15 jobs but some parcels have multiple jobs; categories are property-level here.
ROUTING_MISMATCH_RESOLVED_PARCEL="0905010000300004000"
ROUTING_IDENTITY_TRUE_PARCEL="0905015000500023000"
CHRONOLOGY_INDETERMINATE_PARCEL="0905020000200030000"

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
    for k in ("RECORDDATE","recorddate","record_date"):
        v=p.get(k)
        if v:
            s=str(v)
            if s[:4].isdigit() and len(s)>=10:return s[:10]
    if event_date:
        s=str(event_date)
        if s[:4].isdigit() and len(s)>=10:return s[:10]
    return None

def build_v18j():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,event_date,payload_json
                       FROM evidence_ledger WHERE is_current=1""")
        rows=cur.fetchall()
        cur.execute("""SELECT parcel_id,state,contact_authorized,seller_intent_inferred
                       FROM investigation_state""")
        states=cur.fetchall()

    ev=defaultdict(list)
    for pid,fam,ed,pj in rows: ev[pid].append((fam,ed,_payload(pj)))
    state_map={r[0]:{"state":r[1],"contact_authorized":bool(r[2]),"seller_intent_inferred":bool(r[3])} for r in states}
    parcels=sorted(ev)

    # Reconstruct factual attention context transparently from locked V18C/D principles.
    transfer_counts=[]
    owner_counts=[]
    latest_dates={}
    codes_by={}
    for pid in parcels:
        tr=[x for x in ev[pid] if x[0]=="TRANSFER_TITLE"]
        ow=[x for x in ev[pid] if x[0]=="OWNERSHIP"]
        transfer_counts.append((pid,len(tr))); owner_counts.append((pid,len(ow)))
        ds=[_date(p,e) for _,e,p in tr]; ds=[d for d in ds if d]
        latest_dates[pid]=max(ds) if ds else None
        codes_by[pid]=sorted(set(c for _,_,p in tr if (c:=_code(p))))

    # Locked V18C population thresholds by counts: top factual-depth sets reproduce comparison intent
    # without creating seller scores.
    high_transfer=set(pid for pid,n in sorted(transfer_counts,key=lambda x:(-x[1],x[0]))[:113])
    high_owner=set(pid for pid,n in sorted(owner_counts,key=lambda x:(-x[1],x[0]))[:60])
    rare_codes={"GRT","APD","IAC","PTD","RRD","SHD","SCO","TSC","PRB","CTF","CTC","FCD","EXD","QCD","WRD"}

    # Candidate inclusion is factual and broad: prior INVESTIGATE or unusual/recent/document context.
    candidates=[]
    for pid in parcels:
        st=state_map.get(pid,{"state":"BASELINE","contact_authorized":False,"seller_intent_inferred":False})
        reasons=[]
        if pid in high_transfer: reasons.append("DEEP_TRANSFER_HISTORY_CONTEXT")
        if pid in high_owner: reasons.append("DEEP_OWNERSHIP_RECORD_CONTEXT")
        special=sorted(set(codes_by[pid]) & rare_codes)
        if special: reasons.append("NON_ROUTINE_DOCUMENT_CONTEXT_PRESENT")
        if st["state"]=="INVESTIGATE": reasons.append("EXISTING_GOVERNED_INVESTIGATE_STATE")
        if not reasons: continue

        missing=[]
        if pid in SOURCE_INCOMPLETE_PARCELS:
            missing.append("AUTHORITATIVE_RECORDING_METADATA_INCOMPLETE")
        if pid==CHRONOLOGY_INDETERMINATE_PARCEL:
            missing.append("CHRONOLOGY_RELATIONSHIP_INDETERMINATE")
        if pid==ROUTING_MISMATCH_RESOLVED_PARCEL:
            missing.append("PRIOR_ROUTING_IDENTITY_MISMATCH_RESOLVED_DO_NOT_REUSE_1225700")
        readiness="FACTUAL_FOLLOWUP_REQUIRED" if missing else "CURRENT_MEMORY_READY_FOR_FURTHER_ANALYSIS"

        candidates.append({
          "parcel_id":pid,"investigation_state":st["state"],
          "research_relevance_reasons":reasons,
          "document_codes":codes_by[pid],
          "latest_recorded_transfer_date":latest_dates[pid],
          "factual_readiness":readiness,
          "open_factual_requirements":missing,
          "research_may_continue":True,
          "contact_authorized":False,
          "seller_intent_inferred":False
        })

    counts=defaultdict(int)
    for x in candidates:counts[x["factual_readiness"]]+=1
    return {
      "status":"ok","version":VERSION,"mode":"FACTUAL_READINESS_AND_INVESTIGATION_RELEVANCE_READ_ONLY",
      "summary":{"residential_memory_parcels":len(parcels),"evidence_rows_consumed":len(rows),
        "research_relevant_properties":len(candidates),"readiness_counts":dict(counts),
        "source_incomplete_property_count":sum(1 for x in candidates if "AUTHORITATIVE_RECORDING_METADATA_INCOMPLETE" in x["open_factual_requirements"]),
        "chronology_indeterminate_property_count":sum(1 for x in candidates if "CHRONOLOGY_RELATIONSHIP_INDETERMINATE" in x["open_factual_requirements"]),
        "resolved_routing_mismatch_marked":sum(1 for x in candidates if "PRIOR_ROUTING_IDENTITY_MISMATCH_RESOLVED_DO_NOT_REUSE_1225700" in x["open_factual_requirements"]),
        "database_writes":0},
      "policy":{"missing_data_is_explicit_state":True,"missing_data_blocks_research":False,
        "missing_data_may_require_verification_before_marketing":True,
        "unknown_is_not_silently_filled":True},
      "candidates":candidates,
      "decision_boundary":{"research_layer_only":True,"database_writes":False,
        "seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,"contact_authorized":False,
        "next_step_if_clean":"USE_FACTUAL_READINESS_WITH_CROSS_PROPERTY_CONTEXT_TO_NARROW_RESEARCH_ATTENTION_WITHOUT_EXCLUDING_VERIFICATION_REQUIRED_PROPERTIES"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
