#!/usr/bin/env python3
import json
from db import connect, execute
from eight_delta_event_semantics_v17p import build_eight_delta_event_semantics_v17p

VERSION="V17Q"
MODE="DELTA_SPECIFIC_FACTUAL_RESEARCH_QUESTION_REEVALUATION_PACKETS_READ_ONLY"
MARKET="WESTHAMPTON_BEACH_NY"

def _payload(raw):
    try: return json.loads(raw)
    except Exception: return {}

def _pick(p,*names):
    for n in names:
        if n in p: return p.get(n)
    return None

def _history(parcel_id):
    c=connect()
    try:
        sql="SELECT source_record_id,event_date,payload_json FROM evidence_ledger WHERE market_code=? AND parcel_id=? AND evidence_family='TRANSFER_TITLE' ORDER BY COALESCE(event_date,'') ASC, source_record_id ASC"
        rows=execute(c,sql,(MARKET,parcel_id)).fetchall()
        out=[]
        for r in rows:
            try: sid,event,raw=r["source_record_id"],r["event_date"],r["payload_json"]
            except Exception: sid,event,raw=r[0],r[1],r[2]
            p=_payload(raw)
            out.append({"source_record_id":str(sid) if sid is not None else None,"event_date":event,
              "document_code":_pick(p,"DOCCODE","document_code"),"record_date":_pick(p,"RECORDDATE","record_date"),
              "document_date":_pick(p,"DOCDATE","document_date"),"entry_date":_pick(p,"ENTRYDATE","entry_date"),
              "liber_page":_pick(p,"LIBERPAGE","liber_page")})
        return out
    finally: c.close()

def _counts():
    c=connect()
    try:
        return {"evidence_total":execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0],
          "baseline":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='BASELINE'",(MARKET,)).fetchone()[0],
          "investigate":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(MARKET,)).fetchone()[0]}
    finally: c.close()

def build_delta_specific_research_packets_v17q():
    before=_counts()
    source=build_eight_delta_event_semantics_v17p()
    if source.get("status")!="ok": raise RuntimeError("V17P prerequisite did not return ok")
    packets=[]
    for e in source.get("new_event_packets") or []:
        hist=_history(e["parcel_id"])
        prior=[x for x in hist if str(x.get("source_record_id"))!=str(e.get("source_record_id"))]
        qs=[]
        if e.get("metadata_completion_pending"):
            qs.append({"question":"HAS_COUNTY_COMPLETED_RECORDDATE_AND_LIBERPAGE_FOR_NEW_INSTRUMENT","why":"NEW_SOURCE_IDENTITY_EXISTS_BUT_RECORDING_METADATA_IS_INCOMPLETE"})
        qs.append({"question":"HOW_DOES_NEW_INSTRUMENT_FIT_PRIOR_TITLE_SEQUENCE","why":"NEW_AUTHORITATIVE_SOURCE_IDENTITY_REQUIRES_PROPERTY_HISTORY_CONTEXT"})
        packets.append({"packet_type":"NEW_EVENT_RESEARCH","parcel_id":e["parcel_id"],"source_record_id":e["source_record_id"],
          "document_code":e.get("document_code"),"new_event":{"document_date":e.get("document_date"),"entry_date":e.get("entry_date"),
          "record_date":e.get("record_date"),"liber_page":e.get("liber_page")},"stored_prior_title_event_count":len(prior),
          "recent_prior_title_sequence":prior[-5:],"factual_research_questions":qs,
          "interpretation_limit":"NO_SELLER_INTENT_OR_MOTIVATION_INFERENCE"})
    for e in source.get("existing_event_enrichment_packets") or []:
        hist=_history(e["parcel_id"])
        target=[x for x in hist if str(x.get("source_record_id"))==str(e.get("source_record_id"))]
        packets.append({"packet_type":"EXISTING_EVENT_REEVALUATION","parcel_id":e["parcel_id"],"source_record_id":e["source_record_id"],
          "document_code":e.get("document_code"),"creates_second_event":False,"stored_target_event":target[0] if target else None,
          "authoritative_field_differences":e.get("field_differences"),
          "factual_research_questions":[{"question":"DO_NEWLY_COMPLETED_AUTHORITATIVE_FIELDS_CHANGE_PRIOR_FACTUAL_INTERPRETATION",
          "why":"SAME_SOURCE_IDENTITY_NOW_HAS_MORE_COMPLETE_COUNTY_METADATA"}],
          "interpretation_limit":"METADATA_COMPLETION_IS_NOT_A_SECOND_EVENT"})
    after=_counts()
    return {"status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
      "source_contract":{"version":"V17P","expected_delta_count":8},
      "summary":{"packets_prepared":len(packets),"new_event_research_packets":sum(p["packet_type"]=="NEW_EVENT_RESEARCH" for p in packets),
      "existing_event_reevaluation_packets":sum(p["packet_type"]=="EXISTING_EVENT_REEVALUATION" for p in packets),
      "properties_represented":len(set(p["parcel_id"] for p in packets)),
      "questions_created":sum(len(p["factual_research_questions"]) for p in packets)},
      "research_packets":packets,"protected_counts_before":before,"protected_counts_after":after,"protected_state_unchanged":before==after,
      "decision_boundary":{"research_packets_only":True,"persistence_authorized":False,"investigate_promotion_authorized":False,
      "automatic_external_followup_authorized":False,
      "next_step_if_clean":"EVALUATE_PACKETS_FOR_WHICH_QUESTIONS_CAN_BE_ANSWERED_FROM_EXISTING_MEMORY_VS_REQUIRE_FRESH_SOURCE"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,"seller_intent_inferred":False,
      "seller_scoring":False,"contact_authorized":False,"outreach_touched":False,"clerk_kiosk_scraped":False}}
