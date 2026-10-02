#!/usr/bin/env python3
"""V17L — Full-Universe Re-Evaluation Readiness. Read-only."""
from db import connect, execute

VERSION="V17L"
MODE="FULL_UNIVERSE_REEVALUATION_READINESS_READ_ONLY"
MARKET="WESTHAMPTON_BEACH_NY"

def build_full_universe_reevaluation_readiness_v17l():
    c=connect()
    try:
        evidence_total=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0]
        property_context=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_type=?",(MARKET,"PROPERTY_CONTEXT")).fetchone()[0]
        assessment_context=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_type=?",(MARKET,"ASSESSMENT_CONTEXT")).fetchone()[0]
        ownership=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_type=?",(MARKET,"OWNERSHIP")).fetchone()[0]
        transfer_title=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=? AND evidence_type=?",(MARKET,"TRANSFER_TITLE")).fetchone()[0]
        investigate=execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"INVESTIGATE")).fetchone()[0]
        baseline=execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state=?",(MARKET,"BASELINE")).fetchone()[0]
        research_memory=execute(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(MARKET,)).fetchone()[0]
        verified_controlled=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=? AND controlled_test=1",(MARKET,)).fetchone()[0]
        verified_operational=execute(c,"SELECT COUNT(*) FROM verified_research_evidence WHERE market_code=? AND controlled_test=0",(MARKET,)).fetchone()[0]
    finally:
        c.close()

    residential_universe=property_context
    counts_match_known_baseline=(residential_universe==2082 and evidence_total==18001)
    return {
        "status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
        "universe":{
            "residential_properties":residential_universe,
            "evidence_total":evidence_total,
            "property_context":property_context,
            "assessment_context":assessment_context,
            "ownership":ownership,
            "transfer_title":transfer_title
        },
        "operational_state":{
            "investigate":investigate,
            "baseline":baseline,
            "authoritative_research_memory":research_memory,
            "verified_controlled_test_rows":verified_controlled,
            "verified_operational_rows":verified_operational
        },
        "readiness":{
            "known_baseline_counts_intact":counts_match_known_baseline,
            "full_universe_available_for_change_rescan":residential_universe>0,
            "existing_investigate_state_preserved":True,
            "manual_verification_lane_can_remain_open":True,
            "next_machine_action":"RUN_FACTUAL_CHANGE_RESCAN_WITHOUT_STATE_PROMOTION"
        },
        "guards":{
            "database_writes":False,
            "change_rescan_executed":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False
        }
    }
