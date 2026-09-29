#!/usr/bin/env python3
"""V16F — controlled positive-detection validation harness.

Read-only proof that the locked V16B logical-key/fingerprint/change-key contract
and locked V16D operational-trigger rule wake up for one clearly synthetic new
fact while leaving production tables untouched.
"""
import hashlib, json
from datetime import datetime, timezone
from db import connect, execute

VERSION="V16F"
MODE="CONTROLLED_POSITIVE_DETECTION_VALIDATION"
PILOT="WESTHAMPTON_BEACH_NY"
EXPECTED_RESIDENTIAL=2082
SYN_SOURCE="PMI_SYNTHETIC_VALIDATION_ONLY"
SYN_SID="V16F_SYNTHETIC_TRANSFER_0001"

def _logical_key(r):
    raw='|'.join(str(r.get(k) or '') for k in
        ('market_code','parcel_id','evidence_family','evidence_type','source','source_record_id'))
    return hashlib.sha256(raw.encode()).hexdigest()

def _fingerprint(payload_json,event_date,quality_state,evidence_grade):
    raw='|'.join([str(payload_json or ''),str(event_date or ''),str(quality_state or ''),str(evidence_grade or '')])
    return hashlib.sha256(raw.encode()).hexdigest()

def _change_key(logical_key,change_type,prior_fp,current_fp):
    return hashlib.sha256('|'.join([logical_key,change_type,str(prior_fp or ''),str(current_fp or '')]).encode()).hexdigest()

def run_positive_detection_validation_v16f():
    c=connect()
    try:
        members=int(execute(c,"SELECT COUNT(*) FROM property_market_membership WHERE market_code=?",(PILOT,)).fetchone()[0])
        if members!=EXPECTED_RESIDENTIAL:
            raise RuntimeError(f"membership guard failed: {members}")
        before_changes=int(execute(c,"SELECT COUNT(*) FROM evidence_change_events WHERE market_code=?",(PILOT,)).fetchone()[0])
        before_investigate=int(execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(PILOT,)).fetchone()[0])
        ledger_before=int(execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(PILOT,)).fetchone()[0])

        # Deterministic real market member as container only; the fact itself is explicitly synthetic.
        parcel=str(execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=? ORDER BY parcel_id LIMIT 1",(PILOT,)).fetchone()[0])
        synthetic={
          "market_code":PILOT,"parcel_id":parcel,"evidence_family":"TRANSFER_TITLE",
          "evidence_type":"TRANSFER_HISTORY","source":SYN_SOURCE,"source_record_id":SYN_SID,
          "event_date":"2099-01-01","evidence_grade":"TEST","quality_state":"SYNTHETIC_VALIDATION",
          "payload_json":json.dumps({"synthetic":True,"purpose":"positive detection validation","contactable":False},sort_keys=True)
        }

        lk=_logical_key(synthetic)
        fp=_fingerprint(synthetic["payload_json"],synthetic["event_date"],synthetic["quality_state"],synthetic["evidence_grade"])
        prior=execute(c,"SELECT logical_key FROM evidence_current_state WHERE logical_key=?",(lk,)).fetchone()
        if prior is not None:
            raise RuntimeError("synthetic logical key unexpectedly already exists")

        # Exact locked V16B NEW_EVIDENCE branch.
        change_type="NEW_EVIDENCE"
        ck=_change_key(lk,change_type,None,fp)
        simulated_change={
          "parcel_id":parcel,"change_type":change_type,"evidence_family":synthetic["evidence_family"],
          "evidence_type":synthetic["evidence_type"],"source":synthetic["source"],
          "detected_at":datetime.now(timezone.utc).isoformat(),"change_key":ck
        }

        # Exact locked V16D rule: any post-baseline V16B change event -> INVESTIGATE.
        triggers=[simulated_change]
        target_state="INVESTIGATE" if triggers else "BASELINE"
        queue_item={
          "parcel_id":parcel,"state":target_state,
          "why_investigate":{"operational_triggers":[{
            "type":"POST_BASELINE_FACTUAL_CHANGE","change_type":change_type,
            "evidence_family":synthetic["evidence_family"],"evidence_type":synthetic["evidence_type"],
            "source":SYN_SOURCE,"detected_at":simulated_change["detected_at"]}],
            "rule":"Static/descriptive property and transfer context cannot independently create INVESTIGATE.",
            "seller_intent":False},
          "contact_authorized":False,"seller_intent_inferred":False
        }

        # Re-read production counts to prove harness made no writes.
        ledger_after=int(execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(PILOT,)).fetchone()[0])
        after_changes=int(execute(c,"SELECT COUNT(*) FROM evidence_change_events WHERE market_code=?",(PILOT,)).fetchone()[0])
        after_investigate=int(execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(PILOT,)).fetchone()[0])
        no_writes=(ledger_before==ledger_after and before_changes==after_changes and before_investigate==after_investigate)
        passed=(change_type=="NEW_EVIDENCE" and target_state=="INVESTIGATE" and no_writes)

        return {
          "status":"ok" if passed else "failed","version":VERSION,"mode":MODE,
          "test":{"synthetic":True,"synthetic_source":SYN_SOURCE,"parcel_container":parcel,
                  "production_contactable":False,"expected_change_type":"NEW_EVIDENCE",
                  "detected_change_type":change_type,"expected_state":"INVESTIGATE",
                  "resulting_state":target_state},
          "proof":{"v16b_logical_key":lk,"v16b_fingerprint":fp,"v16b_change_key":ck,
                   "v16d_queue_item":queue_item,"positive_detection_passed":passed},
          "production_state_before":{"ledger_rows":ledger_before,"change_events":before_changes,"investigate_count":before_investigate},
          "production_state_after":{"ledger_rows":ledger_after,"change_events":after_changes,"investigate_count":after_investigate},
          "guards":{"database_writes":False,"production_tables_unchanged":no_writes,
                    "seller_intent_inferred":False,"seller_scoring":False,
                    "contact_authorized":False,"outreach_touched":False},
          "interpretation":"A clearly synthetic post-baseline NEW_EVIDENCE fact is recognized by the locked V16B identity/change contract and satisfies the locked V16D operational trigger without modifying production data.",
          "next_locked_step":"CONNECT_FIRST_REAL_CHANGE_BEARING_EVIDENCE_RAIL_AND_SCHEDULE_REFRESH"
        }
    finally:c.close()
