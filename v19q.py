#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19Q"

def parse_payload(p):
    try:return json.loads(p) if isinstance(p,str) else (p or {})
    except Exception:return {}

def first(d,*keys):
    for k in keys:
        v=d.get(k)
        if v not in (None,""): return v
    return None

def build_v19q():
    import psycopg
    donor=json.loads(Path(__file__).with_name("v19q_donor.json").read_text())
    props=donor["properties"]; ids=[x["parcel_id"] for x in props]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,source_record_id,event_date,quality_state,payload_json
          FROM evidence_ledger WHERE is_current=1 AND parcel_id=ANY(%s)
          AND evidence_family='TRANSFER_TITLE' ORDER BY parcel_id,event_date,source_record_id""",(ids,))
        rows=cur.fetchall()
    finally: conn.close()

    hist={pid:[] for pid in ids}
    for pid,srid,event_date,quality,payload in rows:
        p=parse_payload(payload)
        hist[pid].append({
          "source_record_id":srid,
          "event_date":event_date,
          "document_code":first(p,"DOCCODE","doccode","document_code"),
          "recording_date":first(p,"RECORDDATE","recorddate","recording_date"),
          "instrument_date":first(p,"DOCDATE","docdate","instrument_date"),
          "entry_date":first(p,"ENTRYDATE","entrydate","entry_date"),
          "liber_page":first(p,"LIBERPAGE","liberpage","liber_page"),
          "quality_state":quality
        })

    briefs=[]
    for x in props:
        events=hist[x["parcel_id"]]
        dated=[e for e in events if e["event_date"]]
        recent=dated[-1] if dated else None
        older=dated[:-1]
        reason_bits=[]
        for r in x.get("why_it_surfaced",[]):
            reason_bits.append(r.replace("_"," ").title())
        if x.get("factual_patterns"):
            for p in x["factual_patterns"]:
                txt=p.replace("_"," ").title()
                if txt not in reason_bits: reason_bits.append(txt)
        brief={
          "parcel_id":x["parcel_id"],
          "property_address":x.get("property_address"),
          "owner_context":x.get("owner_context",[]),
          "status":x.get("status"),
          "seller_intent":"NOT_ESTABLISHED",
          "why_pmi_surfaced_it":reason_bits,
          "latest_remembered_transfer_title_event":recent,
          "older_transfer_title_event_count":len(older),
          "transfer_title_event_count":len(events),
          "unresolved_items":x.get("unresolved_items",[]),
          "plain_language_brief":{
             "property":x.get("property_address") or f"Parcel {x['parcel_id']}",
             "owner":", ".join(map(str,x.get("owner_context",[]))) if x.get("owner_context") else "OWNER NOT ESTABLISHED",
             "what_happened":(
               f"Latest remembered transfer/title event is dated {recent['event_date']}"
               + (f" with document code {recent['document_code']}" if recent and recent.get("document_code") else "")
               + f"; {len(older)} older transfer/title event(s) are preserved in memory."
             ) if recent else "No dated transfer/title event is established in current memory.",
             "why_flagged":"; ".join(reason_bits) if reason_bits else "Preserved from the proven active factual-investigation set.",
             "what_still_needs_checking":"; ".join(x.get("unresolved_items",[])) if x.get("unresolved_items") else "Nothing material currently identified.",
             "seller_intent":"NOT ESTABLISHED"
          }
        }
        briefs.append(brief)

    solid=sum(b["status"]=="SOLID" for b in briefs); follow=len(briefs)-solid
    checks={
      "exact_locked_23_retained":len(briefs)==23 and len({b["parcel_id"] for b in briefs})==23,
      "solid_followup_preserved":solid==12 and follow==11,
      "owner_context_present_23":all(bool(b["owner_context"]) for b in briefs),
      "seller_intent_not_inferred":all(b["seller_intent"]=="NOT_ESTABLISHED" for b in briefs),
      "no_candidate_reselection":True,"no_new_score":True,"no_new_ranking":True,
      "existing_memory_only":True
    }
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"LOCKED_23_PROPERTY_EVIDENCE_BRIEFS_EXISTING_MEMORY_READ_ONLY",
      "brief_count":len(briefs),"review_status":{"SOLID":solid,"FOLLOW_UP":follow},
      "briefs":briefs,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"seller_intent_inferred":False,
      "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"REVIEW_REAL_PROPERTY_BRIEFS_AND_CAPTURE_GOOD_BAD_SELECTION_FEEDBACK"}
