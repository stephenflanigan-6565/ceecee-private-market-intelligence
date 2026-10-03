#!/usr/bin/env python3
import json
from pathlib import Path
VERSION="V19F"
def build_v19f():
    d=json.loads(Path(__file__).with_name("v19f_donor.json").read_text())
    pc=d["positive_control"]
    # Controlled synthetic observation mirrors a new authoritative identity,
    # but remains synthetic and therefore can NEVER be persistence-authorized.
    candidate={
      "parcel_id":pc["parcel_id"],
      "source":"Suffolk TaxParcelTransferHistory",
      "source_record_id":pc["source_record_id"],
      "identity_rule":"TRANSHISSEQ",
      "evidence_family":"TRANSFER_TITLE",
      "document_code":pc["doccode"],
      "event_date":pc["recorddate"],
      "recording_date":pc["recorddate"],
      "instrument_date":None,
      "entry_date":None,
      "liber_page":None,
      "completeness_state":"PARTIAL_AUTHORITATIVE_METADATA",
      "provenance_state":"SYNTHETIC_POSITIVE_CONTROL_ONLY",
      "safe_to_remember_as_observation":False,
      "persistence_authorized":False,
      "investigate_promotion_authorized":False,
      "contact_authorized":False,
      "seller_intent_inferred":False
    }
    required=d["memory_candidate_contract"]["required"]
    checks={
      "all_required_fields_present":all(k in candidate for k in required),
      "identity_rule_is_transhisseq":candidate["identity_rule"]=="TRANSHISSEQ",
      "synthetic_candidate_not_persistence_authorized":candidate["persistence_authorized"] is False,
      "synthetic_candidate_not_safe_to_remember":candidate["safe_to_remember_as_observation"] is False,
      "missing_metadata_preserved_not_invented":candidate["liber_page"] is None and candidate["instrument_date"] is None,
      "investigate_not_authorized":candidate["investigate_promotion_authorized"] is False,
      "contact_not_authorized":candidate["contact_authorized"] is False,
      "seller_intent_not_inferred":candidate["seller_intent_inferred"] is False
    }
    passed=all(checks.values())
    return {"status":"ok" if passed else "failed","version":VERSION,
      "mode":"CONTROLLED_MEMORY_UPDATE_CANDIDATE_CONTRACT_READ_ONLY",
      "memory_update_candidate":candidate,"checks":checks,"contract_passed":passed,
      "database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
        "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"VALIDATE_REAL_AUTHORITATIVE_OBSERVATION_MEMORY_CANDIDATE_WITHOUT_PERSISTENCE",
      "next_if_fail":"STOP_AND_REPAIR_MEMORY_CANDIDATE_CONTRACT"}
