#!/usr/bin/env python3
"""V17M1 — Self-Contained Persistent Evidence Factual Rescan.
Read-only. No dependency on legacy change_detection.py.

Purpose:
- Re-evaluate the persisted V16A evidence ledger itself.
- Detect whether a single logical evidence identity currently has more than one
  distinct payload fingerprint in persistent memory.
- Report only factual memory conditions; do not interpret seller intent and do
  not alter investigation state.

This deliberately does NOT fetch external sources. It is the safe first half of
a future refresh cycle: establish whether persistent memory already contains
new/changed factual versions before adding any source refresh authority.
"""
from db import connect, execute

VERSION="V17M1"
MODE="SELF_CONTAINED_PERSISTENT_EVIDENCE_FACTUAL_RESCAN_READ_ONLY"
MARKET="WESTHAMPTON_BEACH_NY"
EXPECTED_FAMILIES={
    "PROPERTY_CONTEXT":2082,
    "ASSESSMENT_CONTEXT":2082,
    "OWNERSHIP":3113,
    "TRANSFER_TITLE":10724,
}

def _scalar(c, sql, params=()):
    return execute(c, sql, params).fetchone()[0]

def build_self_contained_factual_rescan_v17m1():
    c=connect()
    try:
        before={
            "evidence_total":_scalar(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)),
            "baseline":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"BASELINE")),
            "investigate":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"INVESTIGATE")),
            "authoritative_research_memory":_scalar(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,))
        }

        family_counts={}
        for family in EXPECTED_FAMILIES:
            family_counts[family]=_scalar(c,
                "SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_family=?",
                (MARKET,family))

        # V16A's append-safe memory uses evidence_key as stable identity and
        # payload_hash as the normalized factual fingerprint.
        identity_rows=_scalar(c,
            "SELECT COUNT(DISTINCT evidence_key) FROM evidence_ledger WHERE market_code=?",
            (MARKET,))
        identities_with_multiple_payloads=_scalar(c, """
            SELECT COUNT(*) FROM (
                SELECT evidence_key
                FROM evidence_ledger
                WHERE market_code=?
                GROUP BY evidence_key
                HAVING COUNT(DISTINCT payload_hash) > 1
            ) q
        """,(MARKET,))

        changed_family_rows=execute(c, """
            SELECT evidence_family, COUNT(*) AS identity_count
            FROM (
                SELECT evidence_key, MIN(evidence_family) AS evidence_family
                FROM evidence_ledger
                WHERE market_code=?
                GROUP BY evidence_key
                HAVING COUNT(DISTINCT payload_hash) > 1
            ) q
            GROUP BY evidence_family
            ORDER BY evidence_family
        """,(MARKET,)).fetchall()

        changed_by_family={}
        for row in changed_family_rows:
            try:
                family=row["evidence_family"]; count=row["identity_count"]
            except (TypeError, KeyError):
                family=row[0]; count=row[1]
            changed_by_family[str(family)]=int(count)

        after={
            "evidence_total":_scalar(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)),
            "baseline":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"BASELINE")),
            "investigate":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"INVESTIGATE")),
            "authoritative_research_memory":_scalar(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,))
        }
    finally:
        c.close()

    family_counts_intact=all(family_counts.get(k)==v for k,v in EXPECTED_FAMILIES.items())
    protected_state_unchanged=(before==after)
    return {
        "status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
        "dependency_contract":{
            "legacy_change_detection_module_required":False,
            "external_source_fetch":False,
            "database_schema_mutation":False,
            "database_write":False
        },
        "protected_counts_before":before,
        "protected_counts_after":after,
        "persistent_evidence_rescan":{
            "family_counts":family_counts,
            "family_counts_intact":family_counts_intact,
            "distinct_evidence_identities":identity_rows,
            "identities_with_multiple_payload_fingerprints":identities_with_multiple_payloads,
            "changed_identities_by_family":changed_by_family,
            "interpretation":"FACTUAL_MEMORY_VERSION_CHECK_ONLY"
        },
        "readiness":{
            "protected_state_unchanged":protected_state_unchanged,
            "safe_to_add_controlled_source_refresh_next":family_counts_intact and protected_state_unchanged,
            "next_machine_action":"CONTROLLED_SOURCE_REFRESH_DELTA_COMPARISON" if family_counts_intact and protected_state_unchanged else "STOP_AND_REPAIR"
        },
        "guards":{
            "database_writes":False,
            "external_retrievals":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False
        }
    }
