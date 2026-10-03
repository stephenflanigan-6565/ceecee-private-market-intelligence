#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V19G"
def build_v19g():
    d=json.loads(Path(__file__).with_name("v19g_donor.json").read_text())
    o=d["real_authoritative_observation"]
    complete=bool(o.get("recording_date") and o.get("liber_page"))
    candidate={**o,
      "completeness_state":"COMPLETE_AUTHORITATIVE_METADATA" if complete else "PARTIAL_AUTHORITATIVE_METADATA",
      "safe_to_remember_as_observation":True,
      "persistence_authorized":False,
      "investigate_promotion_authorized":False,
      "contact_authorized":False,
      "seller_intent_inferred":False
    }
    checks={
      "real_authoritative_provenance":candidate["provenance_state"]=="AUTHORITATIVE_SUFFOLK_SOURCE_OBSERVATION",
      "identity_rule_is_transhisseq":candidate["identity_rule"]=="TRANSHISSEQ",
      "known_identity_is_1239577":candidate["source_record_id"]=="1239577",
      "known_document_code_is_bsd":candidate["document_code"]=="BSD",
      "known_instrument_date_preserved":candidate["instrument_date"]=="2026-07-09",
      "known_entry_date_preserved":candidate["entry_date"]=="2026-08-31",
      "missing_recording_metadata_preserved":candidate["recording_date"] is None and candidate["liber_page"] is None,
      "partial_metadata_classified":candidate["completeness_state"]=="PARTIAL_AUTHORITATIVE_METADATA",
      "safe_factual_memory_candidate":candidate["safe_to_remember_as_observation"] is True,
      "persistence_still_not_authorized_in_this_test":candidate["persistence_authorized"] is False,
      "investigate_not_authorized":candidate["investigate_promotion_authorized"] is False,
      "contact_not_authorized":candidate["contact_authorized"] is False,
      "seller_intent_not_inferred":candidate["seller_intent_inferred"] is False
    }
    passed=all(checks.values())
    return {"status":"ok" if passed else "failed","version":VERSION,
      "mode":"REAL_AUTHORITATIVE_OBSERVATION_MEMORY_CANDIDATE_VALIDATION_READ_ONLY",
      "memory_update_candidate":candidate,"checks":checks,"real_observation_contract_passed":passed,
      "database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"DESIGN_IDEMPOTENT_FACTUAL_MEMORY_PERSISTENCE_DRY_RUN",
      "next_if_fail":"STOP_AND_REPAIR_REAL_OBSERVATION_MEMORY_CONTRACT"}
