#!/usr/bin/env python3
"""V17I — append-only verified-evidence persistence mechanism test."""
import hashlib, json
from db import connect, execute
from verified_evidence_intake_gate_v17h import build_verified_evidence_intake_gate_v17h

VERSION="V17I"
MODE="VERIFIED_EVIDENCE_APPEND_ONLY_PERSISTENCE_TEST"
MARKET="WESTHAMPTON_BEACH_NY"

def _stable(v):
    return json.dumps(v, sort_keys=True, separators=(",",":"), default=str)

def _key(payload):
    return hashlib.sha256(_stable(payload).encode("utf-8")).hexdigest()

def _ensure_table(c):
    execute(c, """CREATE TABLE IF NOT EXISTS verified_research_evidence (
        evidence_key TEXT PRIMARY KEY,
        market_code TEXT NOT NULL,
        verification_id TEXT NOT NULL,
        parcel_id TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        source_reference TEXT NOT NULL,
        validation_status TEXT NOT NULL,
        controlled_test INTEGER NOT NULL DEFAULT 0,
        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

def build_verified_evidence_persistence_v17i():
    gate=build_verified_evidence_intake_gate_v17h()
    if gate.get("status")!="ok":
        return {"status":"failed","version":VERSION,"error":"V17H prerequisite failed"}

    # This is deliberately NOT represented as a real Clerk verification.
    # It proves storage/idempotency only and is permanently marked controlled_test=1.
    payload={
        "verification_id":"V17I:CONTROLLED:PERSISTENCE:001",
        "parcel_id":"CONTROLLED_TEST_ONLY",
        "evidence_type":"VERIFIED_EVIDENCE_PERSISTENCE_MECHANISM_TEST",
        "return_status":"VERIFIED",
        "source_reference":"CONTROLLED_TEST_SOURCE_NOT_AUTHORITATIVE",
        "fact":"PERSISTENCE_MECHANISM_ONLY",
        "controlled_test":True
    }
    ek=_key(payload)

    c=connect()
    try:
        v16_before=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0]
        v17d_before=execute(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,)).fetchone()[0]
        _ensure_table(c)

        existing=execute(c,"SELECT evidence_key FROM verified_research_evidence WHERE evidence_key=?",(ek,)).fetchone()
        inserted=0
        already=0
        if existing:
            already=1
            execute(c,"UPDATE verified_research_evidence SET last_seen_at=CURRENT_TIMESTAMP WHERE evidence_key=?",(ek,))
        else:
            execute(c, """INSERT INTO verified_research_evidence
                (evidence_key,market_code,verification_id,parcel_id,evidence_type,payload_json,
                 source_reference,validation_status,controlled_test)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (ek,MARKET,payload["verification_id"],payload["parcel_id"],payload["evidence_type"],
                 _stable(payload),payload["source_reference"],"V17H_VALIDATION_CONTRACT_TEST",1))
            inserted=1
        c.commit()

        total=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=?",(MARKET,)).fetchone()[0]
        controlled=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=? AND controlled_test=1",(MARKET,)).fetchone()[0]
        operational=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=? AND controlled_test=0",(MARKET,)).fetchone()[0]
        v16_after=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0]
        v17d_after=execute(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,)).fetchone()[0]
    finally:
        c.close()

    return {
        "status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
        "source_contract":{"version":gate.get("version")},
        "persistence":{
            "table":"verified_research_evidence",
            "inserted_this_run":inserted,
            "already_known_this_run":already,
            "rows_total":total,
            "controlled_test_rows":controlled,
            "operational_verified_rows":operational,
            "idempotent_evidence_key":True,
            "append_only_evidence_model":True,
            "controlled_test_isolated":True
        },
        "protected_counts":{
            "v16a_before":v16_before,"v16a_after":v16_after,
            "v17d_before":v17d_before,"v17d_after":v17d_after,
            "v16a_unchanged":v16_before==v16_after,
            "v17d_unchanged":v17d_before==v17d_after
        },
        "authority":{
            "real_verified_evidence_ingestion_enabled":False,
            "controlled_persistence_test_only":True
        },
        "guards":{
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False,
            "v16a_evidence_ledger_modified":v16_before!=v16_after,
            "v17d_authoritative_memory_modified":v17d_before!=v17d_after
        }
    }
