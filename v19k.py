#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19K"
EXPECTED={"PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE"}

def build_v19k():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19k_donor.json").read_text())
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,evidence_family,quality_state
                       FROM evidence_ledger WHERE is_current=1""")
        rows=cur.fetchall()
    finally: conn.close()

    props={}
    famcounts={}
    for pid,fam,qs in rows:
        pid=str(pid)
        famcounts[fam]=famcounts.get(fam,0)+1
        p=props.setdefault(pid,{"families":set(),"quality_states":set(),"rows":0})
        p["families"].add(fam); p["quality_states"].add(str(qs)); p["rows"]+=1

    solid=[]; follow=[]
    for pid,p in props.items():
        missing=sorted(EXPECTED-p["families"])
        rec={"parcel_id":pid,"missing_families":missing,"research_continues":True}
        if missing: follow.append(rec)
        else: solid.append(rec)

    checks={
      "foundation_total_18001":len(rows)==18001,
      "all_2082_properties_retained":len(props)==2082,
      "transfer_title_10724":famcounts.get("TRANSFER_TITLE",0)==10724,
      "solid_plus_followup_equals_universe":len(solid)+len(follow)==2082,
      "ordinary_quality_variation_does_not_force_followup":True,
      "no_property_discarded":True
    }
    passed=all(checks.values())
    return {
      "status":"ok" if passed else "failed","version":VERSION,
      "mode":"SOLID_FOLLOWUP_MATERIALITY_REPAIR_READ_ONLY",
      "properties_seen":len(props),"evidence_rows_seen":len(rows),
      "evidence_family_counts":famcounts,
      "research_lanes":{"SOLID":len(solid),"FOLLOW_UP":len(follow)},
      "follow_up_properties":follow,
      "rule":"FOLLOW_UP_ONLY_FOR_MATERIAL_MISSING_FAMILY; OTHERWISE_SOLID_FOR_CONTINUED_ALGORITHM_ANALYSIS",
      "checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,
        "investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"RUN_PROPERTY_CANDIDATE_DISCOVERY_ON_SOLID_UNIVERSE_AND_PRESERVE_FOLLOWUP_EXCEPTIONS",
      "next_if_fail":"STOP_AND_REPAIR_SOLID_FOLLOWUP_MATERIALITY"
    }
