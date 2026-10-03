#!/usr/bin/env python3
"""V17V — controlled memory update plan for four resolved existing identities. Dry-run only."""
from v17u import build_v17u
from v17t import build_v17t

VERSION="V17V"
MODE="CONTROLLED_MEMORY_UPDATE_PLAN_DRY_RUN"

def build_v17v():
    u=build_v17u()
    t=build_v17t()
    if u.get("status")!="ok": raise RuntimeError("V17U prerequisite did not return ok")
    fresh_by_id={(str(x.get("parcel_id")),str(x.get("source_record_id"))):x
                 for x in t.get("targeted_gis_results") or []}
    # V17U's four existing events were already retrieved as authoritative deltas before this lane.
    # The plan intentionally updates the known identity rather than creating another event.
    updates=[]
    for x in u.get("existing_event_dispositions") or []:
        updates.append({
          "parcel_id":x.get("parcel_id"),"source_record_id":x.get("source_record_id"),
          "operation":"UPDATE_EXISTING_TRANSFER_TITLE_EVIDENCE_PAYLOAD",
          "identity_semantics":"SAME_SOURCE_IDENTITY",
          "create_new_evidence_row":False,
          "preserve_first_seen":True,
          "refresh_last_seen_on_write":True,
          "fields_authorized":["DOCDATE","LIBERPAGE","RECORDDATE"],
          "write_authorized_in_this_version":False
        })
    excluded=[{"parcel_id":x.get("parcel_id"),"source_record_id":x.get("source_record_id"),
               "reason":"INCOMPLETE_RECORDDATE_AND_LIBERPAGE","write_authorized":False}
              for x in u.get("new_event_open_dispositions") or []]
    return {"status":"ok","version":VERSION,"mode":MODE,
      "source_contract":{"version":"V17U","expected_resolved_existing":4,"expected_open_new":4},
      "summary":{"planned_existing_identity_updates":len(updates),
                 "new_incomplete_identities_excluded":len(excluded),
                 "new_evidence_rows_planned":0,"database_writes":0},
      "memory_update_plan":updates,"excluded_open_identities":excluded,
      "protected_counts_before":u.get("protected_counts_before"),
      "protected_counts_after":u.get("protected_counts_after"),
      "protected_state_unchanged":u.get("protected_state_unchanged"),
      "decision_boundary":{"dry_run_only":True,"persistence_authorized":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"AUTHORIZE_EXACT_FOUR_IDENTITY_MEMORY_UPDATE_WITH_POST_WRITE_IDEMPOTENCE_AND_COUNT_CHECK"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}
