#!/usr/bin/env python3
"""V16D — Operational investigation state + explainable queue.

Creates durable, market-agnostic investigation state without promoting static
property context or descriptive transfer history into seller intent. A property
enters INVESTIGATE only when an operational trigger exists (currently a V16B
post-baseline factual change). Historical V16C reasons remain supporting context.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from db import connect, execute
from opportunity_pathways import build_opportunity_pathways_v16c

VERSION="V16D"
MODE="OPERATIONAL_INVESTIGATION_STATE_AND_EXPLAINABLE_QUEUE"
PILOT="WESTHAMPTON_BEACH_NY"
EXPECTED_RESIDENTIAL=2082

def _now():
    return datetime.now(timezone.utc).isoformat()

def _rows(c, sql, params=()):
    cur=execute(c,sql,params); cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def _ensure_schema(c):
    execute(c, """CREATE TABLE IF NOT EXISTS investigation_state (
      market_code TEXT NOT NULL,
      parcel_id TEXT NOT NULL,
      state TEXT NOT NULL,
      reason_json TEXT NOT NULL,
      trigger_count INTEGER NOT NULL DEFAULT 0,
      first_entered_at TEXT,
      last_evaluated_at TEXT NOT NULL,
      contact_authorized INTEGER NOT NULL DEFAULT 0,
      seller_intent_inferred INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (market_code, parcel_id)
    )""")
    execute(c, """CREATE INDEX IF NOT EXISTS idx_investigation_state_market_state
      ON investigation_state(market_code,state)""")

def build_investigation_queue_v16d():
    # V16C is read-only and gives us the locked interpretation contract.
    v16c=build_opportunity_pathways_v16c()
    c=connect()
    try:
        _ensure_schema(c)
        members=[str(r[0]) for r in execute(c,
          "SELECT parcel_id FROM property_market_membership WHERE market_code=? ORDER BY parcel_id",(PILOT,)).fetchall()]
        if len(members)!=EXPECTED_RESIDENTIAL:
            raise RuntimeError(f"membership guard failed: expected {EXPECTED_RESIDENTIAL}, found {len(members)}")

        # Operational triggers come ONLY from post-baseline V16B change events.
        changes=_rows(c, """SELECT parcel_id,change_type,evidence_family,evidence_type,source,detected_at
          FROM evidence_change_events WHERE market_code=? ORDER BY detected_at,change_key""",(PILOT,))
        by_change=defaultdict(list)
        for x in changes: by_change[str(x["parcel_id"])].append(x)

        # Supporting V16C context is descriptive and cannot independently promote.
        support=defaultdict(list)
        # Recompute bounded-independent reasons directly from current evidence by using
        # V16C preview only would omit most parcels, so use the same factual definitions
        # from current state for queue explanations where a trigger exists.
        states=_rows(c, """SELECT parcel_id,evidence_family,evidence_type,event_date,quality_state
          FROM evidence_current_state WHERE market_code=? AND is_present=1""",(PILOT,))
        by_state=defaultdict(list)
        for x in states: by_state[str(x["parcel_id"])].append(x)

        now=_now()
        created=updated=unchanged=0
        queue=[]
        for pid in members:
            triggers=by_change.get(pid,[])
            target="INVESTIGATE" if triggers else "BASELINE"
            explanation={
              "operational_triggers":[{
                "type":"POST_BASELINE_FACTUAL_CHANGE",
                "change_type":x.get("change_type"),
                "evidence_family":x.get("evidence_family"),
                "evidence_type":x.get("evidence_type"),
                "source":x.get("source"),
                "detected_at":x.get("detected_at")
              } for x in triggers],
              "rule":"Static/descriptive property and transfer context cannot independently create INVESTIGATE.",
              "seller_intent":False
            }
            reason_json=json.dumps(explanation,sort_keys=True,separators=(",",":"))
            old=execute(c,"SELECT state,reason_json,trigger_count,first_entered_at FROM investigation_state WHERE market_code=? AND parcel_id=?",(PILOT,pid)).fetchone()
            if old is None:
                first=now if target=="INVESTIGATE" else None
                execute(c, """INSERT INTO investigation_state
                  (market_code,parcel_id,state,reason_json,trigger_count,first_entered_at,last_evaluated_at,contact_authorized,seller_intent_inferred)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
                  (PILOT,pid,target,reason_json,len(triggers),first,now,0,0))
                created+=1
            else:
                first=old[3]
                if target=="INVESTIGATE" and not first: first=now
                changed=(str(old[0])!=target or str(old[1])!=reason_json or int(old[2] or 0)!=len(triggers))
                execute(c, """UPDATE investigation_state SET state=?,reason_json=?,trigger_count=?,
                  first_entered_at=?,last_evaluated_at=?,contact_authorized=0,seller_intent_inferred=0
                  WHERE market_code=? AND parcel_id=?""",
                  (target,reason_json,len(triggers),first,now,PILOT,pid))
                if changed: updated+=1
                else: unchanged+=1
            if target=="INVESTIGATE":
                queue.append({"parcel_id":pid,"state":"INVESTIGATE","why_investigate":explanation,
                              "contact_authorized":False,"seller_intent_inferred":False})

        c.commit()
        counts={r[0]:int(r[1]) for r in execute(c,
          "SELECT state,COUNT(*) FROM investigation_state WHERE market_code=? GROUP BY state",(PILOT,)).fetchall()}
        return {
          "status":"ok","version":VERSION,"mode":MODE,
          "architecture":{"scope":"SUFFOLK_COUNTY_MULTI_MARKET","pilot_market":PILOT,
            "core_logic_market_agnostic":True,"principle":"BUILD_ONCE_CONFIGURE_BY_MARKET_MEASURE_LOCALLY"},
          "population":{"market_residential_properties":len(members),"all_properties_evaluated":True},
          "state":{"counts":counts,"rows_total":sum(counts.values()),"created_this_run":created,
                   "updated_this_run":updated,"unchanged_this_run":unchanged},
          "operational_triggers":{"v16b_change_events_available":len(changes),
             "properties_with_post_baseline_change":len(by_change),
             "investigate_requires_operational_trigger":True},
          "queue":{"investigate_count":len(queue),"returned":min(50,len(queue)),
                   "ordering":"DETECTED_CHANGE_THEN_PARCEL_NOT_SELLER_RANKING","properties":queue[:50]},
          "v16c_context":{"properties_with_research_reasons":v16c["population"]["properties_with_one_or_more_research_reasons"],
                          "properties_with_no_current_research_reason":v16c["population"]["properties_with_no_current_research_reason"],
                          "historical_research_reason_is_not_investigate_trigger":True},
          "guards":{"seller_scoring":False,"seller_probability":False,"seller_intent_inferred":False,
                    "contact_authorized":False,"outreach_touched":False,
                    "price_floor":False,"luxury_floor":False,"property_size_floor":False,
                    "geographic_prestige_requirement":False},
          "interpretation":["INVESTIGATE means investigate, not seller.",
             "No property is promoted merely because it is old, large, expensive, prestigious, or has a long transfer gap.",
             "A zero-item INVESTIGATE queue is valid when no post-baseline operational evidence has changed.",
             "Contact remains downstream of ownership verification and Contact Governor."],
          "next_locked_step":"V16E_CONNECT_FIRST_HIGH_VALUE_SELLER_RELEVANT_EVIDENCE_RAIL_AFTER_V16D_VERIFICATION"
        }
    finally:
        c.close()
