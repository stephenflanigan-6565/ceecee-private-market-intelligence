#!/usr/bin/env python3
"""V16G — scheduled pipeline runner foundation.

One guarded invocation runs the already-proven live Suffolk refresh and then the
locked V16A -> V16B -> V16C -> V16D chain. It does not create an external
scheduler; it creates the single safe endpoint that a scheduler can call.
"""
from datetime import datetime, timezone
from live_evidence_refresh_v16e4c import refresh_suffolk_live_evidence_v16e4b
from evidence_memory import build_evidence_memory_v16a
from change_detection import build_change_detection_v16b
from opportunity_pathways import build_opportunity_pathways_v16c
from investigation_queue import build_investigation_queue_v16d

VERSION="V16G"
MODE="GUARDED_AUTOMATED_INTELLIGENCE_PIPELINE_RUNNER"

def _ok(x): return isinstance(x,dict) and x.get("status")=="ok"

def run_guarded_pipeline_v16g():
    started=datetime.now(timezone.utc).isoformat()
    stages=[]

    refresh=refresh_suffolk_live_evidence_v16e4b()
    stages.append({"stage":"V16E4c_LIVE_REFRESH","status":refresh.get("status"),
                   "new_source_rows_total":(refresh.get("persistence") or {}).get("new_source_rows_total")})
    if not _ok(refresh): return _stop(started,stages,"V16E4c")

    memory=build_evidence_memory_v16a()
    stages.append({"stage":"V16A_EVIDENCE_MEMORY","status":memory.get("status"),
                   "inserted_this_run":(memory.get("evidence_memory") or {}).get("inserted_this_run")})
    if not _ok(memory): return _stop(started,stages,"V16A")

    changes=build_change_detection_v16b()
    comp=changes.get("comparison") or {}
    stages.append({"stage":"V16B_CHANGE_DETECTION","status":changes.get("status"),
                   "changes_created_this_run":comp.get("changes_created_this_run")})
    if not _ok(changes): return _stop(started,stages,"V16B")

    context=build_opportunity_pathways_v16c()
    stages.append({"stage":"V16C_INTERPRETATION","status":context.get("status"),
                   "properties_with_change_events":(context.get("change_memory") or {}).get("properties_with_change_events")})
    if not _ok(context): return _stop(started,stages,"V16C")

    queue=build_investigation_queue_v16d()
    q=queue.get("queue") or {}
    stages.append({"stage":"V16D_INVESTIGATION_QUEUE","status":queue.get("status"),
                   "investigate_count":q.get("investigate_count")})
    if not _ok(queue): return _stop(started,stages,"V16D")

    investigate=int(q.get("investigate_count") or 0)
    new_changes=int(comp.get("changes_created_this_run") or 0)
    return {"status":"ok","version":VERSION,"mode":MODE,"started_at":started,
      "completed_at":datetime.now(timezone.utc).isoformat(),"stages":stages,
      "result":{"new_change_events":new_changes,"investigate_count":investigate,
                "attention_required":bool(new_changes or investigate),
                "delivery_state":"READY_FOR_AGENT_DELIVERY" if investigate else "QUIET_NO_ACTION"},
      "guards":{"stop_on_stage_failure":True,"contact_authorized":False,"outreach_touched":False,
                "seller_intent_inferred":False,"seller_scoring":False},
      "next_locked_step":"CONNECT_EXTERNAL_SCHEDULE_AND_AGENT_DELIVERY_ONLY_AFTER_V16G_VERIFICATION"}

def _stop(started,stages,failed):
    return {"status":"degraded","version":VERSION,"mode":MODE,"started_at":started,
      "completed_at":datetime.now(timezone.utc).isoformat(),"failed_stage":failed,"stages":stages,
      "result":{"attention_required":True,"delivery_state":"PIPELINE_FAILURE_REQUIRES_REVIEW"},
      "guards":{"stop_on_stage_failure":True,"contact_authorized":False,"outreach_touched":False,
                "seller_intent_inferred":False,"seller_scoring":False}}
