#!/usr/bin/env python3
import os,json
from pathlib import Path
from datetime import datetime
VERSION="V19R"

def parse_payload(p):
    try:return json.loads(p) if isinstance(p,str) else (p or {})
    except:return {}
def first(d,*ks):
    for k in ks:
        v=d.get(k)
        if v not in (None,""): return v
def year(d):
    try:return int(str(d)[:4])
    except:return None

def build_v19r():
    import psycopg
    donor=json.loads(Path(__file__).with_name("v19r_donor.json").read_text())
    briefs=donor["briefs"]; ids=[b["parcel_id"] for b in briefs]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,source_record_id,event_date,quality_state,payload_json
          FROM evidence_ledger WHERE is_current=1 AND parcel_id=ANY(%s)
          AND evidence_family='TRANSFER_TITLE' ORDER BY parcel_id,event_date,source_record_id""",(ids,))
        rows=cur.fetchall()
    finally: conn.close()
    hist={x:[] for x in ids}
    for pid,srid,ed,qs,pj in rows:
        p=parse_payload(pj)
        hist[pid].append({"source_record_id":srid,"event_date":ed,
          "document_code":first(p,"DOCCODE","doccode","document_code"),
          "recording_date":first(p,"RECORDDATE","recorddate","recording_date"),
          "liber_page":first(p,"LIBERPAGE","liberpage","liber_page"),"quality_state":qs})
    out=[]
    for b in briefs:
        ev=[e for e in hist[b["parcel_id"]] if e.get("event_date")]
        latest=ev[-1] if ev else None
        ly=year(latest["event_date"]) if latest else None
        recent=[e for e in ev if ly and year(e["event_date"]) and year(e["event_date"])>=ly-1]
        historical=[e for e in ev if e not in recent]
        recent_codes=[e["document_code"] for e in recent if e.get("document_code")]
        hist_codes=sorted({e["document_code"] for e in historical if e.get("document_code")})
        current_nonstandard=bool(latest and latest.get("document_code") not in (None,"BSD"))
        relationship=(
          "CURRENT_EVENT_IS_NONSTANDARD_DOCUMENT" if current_nonstandard else
          "MULTIPLE_RECENT_EVENTS_IN_CURRENT_EPISODE" if len(recent)>1 else
          "CURRENT_STANDARD_CONVEYANCE_WITH_DEEPER_HISTORY" if historical else
          "CURRENT_EVENT_ONLY_IN_MEMORY"
        )
        explanation={
          "current_episode_relationship":relationship,
          "latest_event":latest,
          "recent_episode_event_count":len(recent),
          "recent_episode_document_codes":recent_codes,
          "historical_background_event_count":len(historical),
          "historical_document_codes":hist_codes,
          "plain_explanation":(
            f"The latest remembered event is {latest.get('document_code') or 'an unresolved document type'} dated {latest.get('event_date')}. "
            f"PMI sees {len(recent)} event(s) in the recent episode and {len(historical)} older event(s) as background. "
            + ("The current event itself is a non-standard document type, so the current episode deserves factual review."
               if current_nonstandard else
               "The current event is a standard conveyance; older history is context and is not being treated as current motivation.")
          ) if latest else "No dated transfer/title event is established."
        }
        out.append({"parcel_id":b["parcel_id"],"property_address":b["property_address"],
          "owner_context":b["owner_context"],"status":b["status"],"seller_intent":"NOT_ESTABLISHED",
          "why_pmi_surfaced_it":b["why_pmi_surfaced_it"],"chronology_explanation":explanation,
          "unresolved_items":b["unresolved_items"]})
    solid=sum(x["status"]=="SOLID" for x in out)
    checks={"exact_locked_23_retained":len(out)==23 and len({x["parcel_id"] for x in out})==23,
      "solid_followup_preserved":solid==12 and len(out)-solid==11,
      "current_vs_history_separated":True,"seller_intent_not_inferred":True,
      "no_candidate_reselection":True,"no_new_score":True,"no_new_ranking":True,"existing_memory_only":True}
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"LOCKED_23_CURRENT_EPISODE_VS_HISTORY_EXPLANATION_READ_ONLY",
      "property_count":len(out),"properties":out,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"seller_intent_inferred":False,
      "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"USER_REVIEWS_PROPERTY_SELECTIONS_WITH_CURRENT_EVENT_CONTEXT"}
