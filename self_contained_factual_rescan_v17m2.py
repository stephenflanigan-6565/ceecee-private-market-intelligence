#!/usr/bin/env python3
"""V17M2 — Self-Contained Persistent Evidence Factual Rescan.
Uses exact V16A evidence_ledger schema. Read-only.
"""
from db import connect, execute

VERSION="V17M2"
MODE="SELF_CONTAINED_PERSISTENT_EVIDENCE_FACTUAL_RESCAN_V16A_SCHEMA"
MARKET="WESTHAMPTON_BEACH_NY"
EXPECTED_FAMILIES={
    "PROPERTY_CONTEXT":2082,
    "ASSESSMENT_CONTEXT":2082,
    "OWNERSHIP":3113,
    "TRANSFER_TITLE":10724,
}

def _scalar(c,sql,params=()):
    return execute(c,sql,params).fetchone()[0]

def build_self_contained_factual_rescan_v17m2():
    c=connect()
    try:
        before={
            "evidence_total":_scalar(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)),
            "baseline":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"BASELINE")),
            "investigate":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"INVESTIGATE")),
            "authoritative_research_memory":_scalar(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,))
        }
        family_counts={f:_scalar(c,
            "SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_family=?",(MARKET,f))
            for f in EXPECTED_FAMILIES}

        current_rows=_scalar(c,
            "SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND is_current=1",(MARKET,))
        noncurrent_rows=_scalar(c,
            "SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND is_current<>1",(MARKET,))
        rows_with_source_record_id=_scalar(c,
            """SELECT COUNT(*) FROM evidence_ledger
               WHERE market_code=? AND source_record_id IS NOT NULL
               AND TRIM(source_record_id)<>''""",(MARKET,))
        rows_without_source_record_id=_scalar(c,
            """SELECT COUNT(*) FROM evidence_ledger
               WHERE market_code=? AND (source_record_id IS NULL OR TRIM(source_record_id)='')""",(MARKET,))

        # Exact V16A semantics: evidence_key includes normalized payload. Therefore,
        # multiple evidence_key values for the same stable source identity mean
        # persistent memory contains multiple factual payload versions for that source record.
        multi_version_source_identities=_scalar(c, """
            SELECT COUNT(*) FROM (
              SELECT parcel_id,evidence_family,source,source_record_id
              FROM evidence_ledger
              WHERE market_code=? AND source_record_id IS NOT NULL AND TRIM(source_record_id)<>''
              GROUP BY parcel_id,evidence_family,source,source_record_id
              HAVING COUNT(DISTINCT evidence_key)>1 OR COUNT(DISTINCT payload_json)>1
            ) q
        """,(MARKET,))

        rows=execute(c, """
            SELECT evidence_family, COUNT(*) AS identity_count
            FROM (
              SELECT parcel_id,evidence_family,source,source_record_id
              FROM evidence_ledger
              WHERE market_code=? AND source_record_id IS NOT NULL AND TRIM(source_record_id)<>''
              GROUP BY parcel_id,evidence_family,source,source_record_id
              HAVING COUNT(DISTINCT evidence_key)>1 OR COUNT(DISTINCT payload_json)>1
            ) q
            GROUP BY evidence_family
            ORDER BY evidence_family
        """,(MARKET,)).fetchall()
        by_family={}
        for r in rows:
            try: fam,cnt=r["evidence_family"],r["identity_count"]
            except (TypeError,KeyError): fam,cnt=r[0],r[1]
            by_family[str(fam)]=int(cnt)

        after={
            "evidence_total":_scalar(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)),
            "baseline":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"BASELINE")),
            "investigate":_scalar(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"INVESTIGATE")),
            "authoritative_research_memory":_scalar(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,))
        }
    finally:
        c.close()

    family_ok=all(family_counts.get(k)==v for k,v in EXPECTED_FAMILIES.items())
    protected=(before==after)
    return {
      "status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
      "schema_contract":{
        "source":"V16A_PERSISTENT_EVIDENCE_MEMORY_FOUNDATION",
        "stable_key_field":"evidence_key",
        "payload_field":"payload_json",
        "source_identity_field":"source_record_id",
        "current_marker_field":"is_current",
        "assumed_hash_column":False
      },
      "protected_counts_before":before,
      "protected_counts_after":after,
      "persistent_evidence_rescan":{
        "family_counts":family_counts,
        "family_counts_intact":family_ok,
        "current_rows":current_rows,
        "noncurrent_rows":noncurrent_rows,
        "rows_with_source_record_id":rows_with_source_record_id,
        "rows_without_source_record_id":rows_without_source_record_id,
        "source_identities_with_multiple_persisted_payload_versions":multi_version_source_identities,
        "multi_version_identities_by_family":by_family,
        "meaning":"PERSISTENT_MEMORY_VERSION_CHECK_NOT_EXTERNAL_REFRESH"
      },
      "readiness":{
        "protected_state_unchanged":protected,
        "safe_to_add_controlled_source_refresh_next":family_ok and protected,
        "next_machine_action":"CONTROLLED_SOURCE_REFRESH_DELTA_COMPARISON" if family_ok and protected else "STOP_AND_REPAIR"
      },
      "guards":{
        "database_writes":False,"external_retrievals":False,
        "investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,
        "contact_authorized":False,"outreach_touched":False
      }
    }
