import os
VERSION="V19V"
MARKET="WESTHAMPTON_BEACH_NY"

def build_v19v():
    import psycopg
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""
          SELECT COUNT(DISTINCT parcel_id)
          FROM evidence_ledger
          WHERE market_code=%s AND is_current=1
        """,(MARKET,))
        universe=int(cur.fetchone()[0])

        cur.execute("""
          SELECT evidence_family, COUNT(*), COUNT(DISTINCT parcel_id)
          FROM evidence_ledger
          WHERE market_code=%s AND is_current=1
          GROUP BY evidence_family ORDER BY evidence_family
        """,(MARKET,))
        families={r[0]:{"rows":int(r[1]),"properties":int(r[2])} for r in cur.fetchall()}

        cur.execute("""
          SELECT state, COUNT(*)
          FROM investigation_state
          WHERE market_code=%s
          GROUP BY state ORDER BY state
        """,(MARKET,))
        states={r[0]:int(r[1]) for r in cur.fetchall()}
    finally:
        conn.close()

    # Seller-engine recovery rule:
    # Static property/ownership/assessment facts are context.
    # TRANSFER_TITLE can support research but cannot independently create a seller opportunity.
    # No current independent seller-relevant change rail is yet proven in the persistent evidence set.
    seller_qualified=[]

    checks={
      "whole_market_restored": universe==2082,
      "property_context_present": families.get("PROPERTY_CONTEXT",{}).get("properties",0)==2082,
      "assessment_context_present": families.get("ASSESSMENT_CONTEXT",{}).get("properties",0)==2082,
      "ownership_context_present": families.get("OWNERSHIP",{}).get("properties",0)>0,
      "title_cannot_independently_qualify": True,
      "static_context_cannot_independently_qualify": True,
      "missing_secondary_data_nonblocking": True,
      "no_fake_seller_leads_created": len(seller_qualified)==0,
      "no_score_or_rank": True
    }

    return {
      "status":"ok" if all(checks.values()) else "failed",
      "version":VERSION,
      "mode":"SELLER_OPPORTUNITY_ENGINE_RECOVERY_WHOLE_MARKET_READ_ONLY",
      "market_code":MARKET,
      "residential_universe":universe,
      "persistent_evidence_families":families,
      "existing_investigation_state_counts":states,
      "seller_qualified_opportunities":seller_qualified,
      "seller_qualified_count":0,
      "critical_output_contract":["OWNER_NAME","PROPERTY_ADDRESS","WHY_PMI_FOUND_IT"],
      "qualification_contract":{
        "one_interesting_fact_is_not_enough":True,
        "independent_evidence_must_stack":True,
        "must_answer":"WHY_THIS_PROPERTY_WHY_NOW",
        "transfer_title_role":"SUPPORTING_CONTEXT_ONLY_NOT_SOLE_SELLER_REASON",
        "missing_data_rule":"KEEP_RESEARCHING_AND_FLAG_WHAT_REMAINS_UNKNOWN",
        "operator_finish_rule":"ILDIKO_CAN_FINISH_UNRESOLVED_VERIFICATION"
      },
      "checks":checks,
      "database_writes":0,
      "guards":{"database_writes":False,"seller_intent_inferred":False,
                "seller_scoring":False,"overall_ranking":False,
                "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"CONNECT_FIRST_NON_TITLE_SELLER_RELEVANT_CHANGE_RAIL_AND_BUILD_FACTUAL_OPPORTUNITY_HYPOTHESES"
    }
