#!/usr/bin/env python3
"""V17L1 — Full-Universe Re-Evaluation Readiness repair. Read-only."""
from db import connect, execute

VERSION="V17L1"
MODE="FULL_UNIVERSE_REEVALUATION_READINESS_EVIDENCE_FAMILY_REPAIR"
MARKET="WESTHAMPTON_BEACH_NY"

def _family_count(c, family):
    return execute(c,
        "SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_family=?",
        (MARKET,family)).fetchone()[0]

def build_full_universe_reevaluation_readiness_v17l1():
    c=connect()
    try:
        evidence_total=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0]
        property_context=_family_count(c,"PROPERTY_CONTEXT")
        assessment_context=_family_count(c,"ASSESSMENT_CONTEXT")
        ownership=_family_count(c,"OWNERSHIP")
        transfer_title=_family_count(c,"TRANSFER_TITLE")
        investigate=execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"INVESTIGATE")).fetchone()[0]
        baseline=execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"BASELINE")).fetchone()[0]
        research_memory=execute(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,)).fetchone()[0]
        verified_controlled=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=? AND controlled_test=1",(MARKET,)).fetchone()[0]
        verified_operational=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=? AND controlled_test=0",(MARKET,)).fetchone()[0]
    finally:
        c.close()

    state_universe=baseline+investigate
    family_counts_match=(property_context==2082 and assessment_context==2082 and ownership==3113 and transfer_title==10724)
    totals_match=(evidence_total==18001 and state_universe==2082)
    return {
        "status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
        "repair":{"failed_version":"V17L","defect":"QUERIED_EVIDENCE_TYPE_INSTEAD_OF_EVIDENCE_FAMILY",
                  "repair_scope":"CATEGORY_COUNTING_ONLY"},
        "universe":{
            "residential_properties":property_context,
            "state_universe":state_universe,
            "evidence_total":evidence_total,
            "property_context":property_context,
            "assessment_context":assessment_context,
            "ownership":ownership,
            "transfer_title":transfer_title
        },
        "operational_state":{
            "baseline":baseline,"investigate":investigate,
            "authoritative_research_memory":research_memory,
            "verified_controlled_test_rows":verified_controlled,
            "verified_operational_rows":verified_operational
        },
        "readiness":{
            "known_family_counts_intact":family_counts_match,
            "known_total_counts_intact":totals_match,
            "full_universe_available_for_change_rescan":family_counts_match and totals_match,
            "existing_investigate_state_preserved":True,
            "manual_verification_lane_can_remain_open":True,
            "next_machine_action":"RUN_FACTUAL_CHANGE_RESCAN_WITHOUT_STATE_PROMOTION"
        },
        "guards":{
            "database_writes":False,"change_rescan_executed":False,
            "investigate_state_touched":False,"new_candidate_created":False,
            "seller_intent_inferred":False,"seller_scoring":False,
            "contact_authorized":False,"outreach_touched":False
        }
    }
