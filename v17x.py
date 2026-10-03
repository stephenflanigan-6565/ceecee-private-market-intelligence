#!/usr/bin/env python3
"""V17X — four incomplete new identities watch-state persistence readiness. Dry-run only."""
VERSION="V17X"
TARGETS=[
 {"parcel_id":"0905008000100029002","source_record_id":"1243777","doccode":"WRD","docdate":"2026-08-12","entrydate":"2026-09-28"},
 {"parcel_id":"0905012030200002000","source_record_id":"1243879","doccode":"BSD","docdate":None,"entrydate":"2026-09-28"},
 {"parcel_id":"0905018000200014000","source_record_id":"1244200","doccode":"BSD","docdate":"2026-08-11","entrydate":"2026-09-29"},
 {"parcel_id":"0905020000100004000","source_record_id":"1244373","doccode":"BSD","docdate":"2026-08-03","entrydate":"2026-09-30"},
]
def build_v17x():
    watches=[]
    for t in TARGETS:
        watches.append({**t,
          "watch_state":"AWAITING_AUTHORITATIVE_RECORDING_METADATA_COMPLETION",
          "missing_fields":["RECORDDATE","LIBERPAGE"],
          "open_questions":[
            "HAS_COUNTY_COMPLETED_RECORDDATE_AND_LIBERPAGE_FOR_NEW_INSTRUMENT",
            "HOW_DOES_NEW_INSTRUMENT_FIT_PRIOR_TITLE_SEQUENCE"],
          "recheck_source":"SUFFOLK_COUNTY_GIS_TRANSFER_HISTORY",
          "identity_is_known":True,
          "entrydate_not_recorddate":True,
          "investigate_authority":False})
    return {"status":"ok","version":VERSION,
      "mode":"INCOMPLETE_NEW_IDENTITY_WATCH_STATE_PERSISTENCE_READINESS_DRY_RUN",
      "summary":{"watch_identities":4,"open_questions":8,"database_writes":0,
                 "investigate_promotions":0},
      "watch_records":watches,
      "decision_boundary":{"dry_run_only":True,"persistence_authorized":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"PERSIST_EXACT_FOUR_OPEN_RESEARCH_WATCH_IDENTITIES_IDEMPOTENTLY"},
      "guards":{"database_writes":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}
