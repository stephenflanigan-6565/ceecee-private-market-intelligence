#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V18Y"
def build_v18y():
    d=json.loads((Path(__file__).with_name("v18y_donor.json")).read_text())
    o=d["proven_v18x1_observation"]
    missing=[k for k in ("recorddate","liberpage") if o.get(k) is None]
    return {
      "status":"ok","version":VERSION,
      "mode":"V18X1_FACTUAL_OBSERVATION_REEVALUATION_CLOSEOUT_READ_ONLY",
      "parcel_id":d["parcel_id"],
      "new_factual_observation":o,
      "memory_update_candidate":{
        "identity":o["source_record_id"],
        "evidence_family":"TRANSFER_TITLE",
        "source":o["source"],
        "quality_state":"PARTIAL_AUTHORITATIVE_METADATA",
        "missing_fields":missing,
        "safe_to_remember_as_observation":True
      },
      "reevaluation":{
        "prior_unresolved_fact":"RECENT_TRANSFER_SEQUENCE_NOT_PRESENT_IN_V18E_MEMORY",
        "result":"RECENT_TRANSFER_ACTIVITY_FACTUALLY_CONFIRMED",
        "current_event_semantics":"CURRENT_CONVEYANCE_EVENT_METADATA_INCOMPLETE",
        "remaining_fact_gap":"AUTHORITATIVE_RECORDING_DATE_AND_LIBERPAGE",
        "broad_automated_search_needed":False,
        "exception_branch_status":"CLOSED_FROM_AUTOMATED_BROAD_RESEARCH",
        "research_may_continue":True
      },
      "next_system_scope":"RETURN_TO_FULL_2082_PROPERTY_UNIVERSE",
      "database_writes":0,
      "guards":{"database_writes":False,"external_calls":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False}
    }
