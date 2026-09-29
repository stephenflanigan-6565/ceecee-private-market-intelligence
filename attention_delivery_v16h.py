#!/usr/bin/env python3
"""V16H — attention delivery payload.

Runs the locked V16G pipeline and converts its result into a compact delivery
contract. Quiet runs create no agent alert. INVESTIGATE runs produce an
explainable payload; failures produce an operator alert. No external message is
sent by this module.
"""
from datetime import datetime, timezone
from automated_pipeline_v16g import run_guarded_pipeline_v16g
from investigation_queue import build_investigation_queue_v16d

VERSION="V16H"
MODE="ATTENTION_ONLY_DELIVERY_PAYLOAD"

def build_attention_delivery_v16h():
    run=run_guarded_pipeline_v16g()
    now=datetime.now(timezone.utc).isoformat()

    if run.get("status")!="ok":
        return {
          "status":"ok","version":VERSION,"mode":MODE,"generated_at":now,
          "delivery":{"send":True,"audience":"OPERATOR","type":"PIPELINE_FAILURE",
                      "subject":"Private Market Intelligence pipeline needs review",
                      "body":{"failed_stage":run.get("failed_stage"),"stages":run.get("stages",[])}},
          "pipeline":run,
          "guards":{"external_message_sent":False,"contact_authorized":False,
                    "outreach_touched":False,"seller_intent_inferred":False,"seller_scoring":False},
          "next_locked_step":"CONNECT_SCHEDULER_AND_NOTIFICATION_TRANSPORT_AFTER_V16H_VERIFICATION"}

    result=run.get("result") or {}
    if not result.get("attention_required"):
        return {
          "status":"ok","version":VERSION,"mode":MODE,"generated_at":now,
          "delivery":{"send":False,"audience":None,"type":"QUIET_NO_ACTION",
                      "subject":None,"body":None},
          "pipeline_summary":{"delivery_state":result.get("delivery_state"),
                              "new_change_events":result.get("new_change_events",0),
                              "investigate_count":result.get("investigate_count",0),
                              "stages":run.get("stages",[])},
          "guards":{"external_message_sent":False,"contact_authorized":False,
                    "outreach_touched":False,"seller_intent_inferred":False,"seller_scoring":False},
          "next_locked_step":"CONNECT_SCHEDULER_AND_NOTIFICATION_TRANSPORT_AFTER_V16H_VERIFICATION"}

    # Re-read locked V16D queue after V16G completed so delivery uses the durable,
    # explainable operational state rather than reconstructing seller logic here.
    q=build_investigation_queue_v16d()
    props=(q.get("queue") or {}).get("properties") or []
    items=[]
    for p in props:
        items.append({
          "parcel_id":p.get("parcel_id"),
          "state":p.get("state","INVESTIGATE"),
          "why_investigate":p.get("why_investigate"),
          "contact_authorized":False,
          "seller_intent_inferred":False
        })
    return {
      "status":"ok","version":VERSION,"mode":MODE,"generated_at":now,
      "delivery":{"send":True,"audience":"AGENT","type":"INVESTIGATION_QUEUE",
                  "subject":f"Private Market Intelligence: {len(items)} item(s) to investigate",
                  "body":{"investigate_count":len(items),"items":items}},
      "pipeline_summary":{"delivery_state":result.get("delivery_state"),
                          "new_change_events":result.get("new_change_events",0),
                          "investigate_count":result.get("investigate_count",0),
                          "stages":run.get("stages",[])},
      "guards":{"external_message_sent":False,"contact_authorized":False,
                "outreach_touched":False,"seller_intent_inferred":False,"seller_scoring":False},
      "next_locked_step":"CONNECT_SCHEDULER_AND_NOTIFICATION_TRANSPORT_AFTER_V16H_VERIFICATION"}
