#!/usr/bin/env python3
import os,json
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date
VERSION="V19B1"

def _j(s):
    try: return json.loads(s or "{}")
    except Exception: return {}

def _norm(v):
    if v is None:return None
    s=str(v).strip()
    return s or None

def _date(v):
    s=_norm(v)
    if not s:return None
    try:return date.fromisoformat(s[:10])
    except Exception:return None

def _field(p,*names):
    low={str(k).lower():v for k,v in p.items()}
    for n in names:
        v=low.get(n.lower())
        if v not in (None,""): return v
    return None

def build_v19b():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19b1_donor.json").read_text())
    market=d["market_code"]; cutoff=date.fromisoformat(d["current_cutoff"])
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,evidence_family,evidence_type,source_record_id,event_date,quality_state,payload_json
                       FROM evidence_ledger WHERE market_code=%s AND is_current=1
                       ORDER BY parcel_id,evidence_family,evidence_key""",(market,))
        rows=cur.fetchall()
    finally: conn.close()

    by=defaultdict(list); families=Counter()
    for parcel,fam,evidence_type,sid,event_date,quality,payload in rows:
        families[fam]+=1
        if fam=="TRANSFER_TITLE":
            # Consume the normalized persistent-memory abstraction.
            # evidence_type is the normalized transfer/title document code;
            # event_date is the normalized chronology date; quality_state preserves source completeness.
            dt=_date(event_date)
            code=_norm(evidence_type)
            by[parcel].append({"source_record_id":_norm(sid),"event_date":str(event_date) if event_date else None,
              "dt":dt,"doccode":code,"quality_state":quality})
        else:
            by.setdefault(parcel,[])

    counts=Counter(); outputs=[]; checks=set(d["known_semantic_checks"])
    current_props=0
    for parcel,trs in sorted(by.items()):
        dated=[x for x in trs if x["dt"]]
        current=[x for x in dated if x["dt"]>=cutoff]
        historical=[x for x in dated if x["dt"]<cutoff]
        if not current:
            state="NO_CURRENT_TRANSFER_EPISODE"
            if not trs: state="NO_TRANSFER_TITLE_MEMORY"
        else:
            current_props+=1
            latest=max(x["dt"] for x in current)
            episode=[x for x in current if x["dt"]==latest]
            codes=[x["doccode"] for x in episode if x["doccode"]]
            incomplete=any(str(x.get("quality_state") or "").upper() not in ("VALID","COMPLETE","VERIFIED") for x in episode)
            nonstd=any(c!="BSD" for c in codes)
            hist_nonstd=any(x["doccode"] and x["doccode"]!="BSD" for x in historical)
            if len(episode)>1:
                state="CURRENT_MULTI_DOCUMENT_SAME_DAY_EPISODE"
            elif incomplete:
                state="CURRENT_EVENT_METADATA_INCOMPLETE"
            elif nonstd:
                state="CURRENT_NON_STANDARD_EVENT"
            elif hist_nonstd:
                state="CURRENT_CONVEYANCE_WITH_HISTORICAL_NONSTANDARD_BACKGROUND"
            else:
                state="CURRENT_STANDARD_CONVEYANCE_CONTEXT"
        counts[state]+=1
        if parcel in checks:
            latest_events=[]
            if current:
                latest=max(x["dt"] for x in current)
                latest_events=[{k:v for k,v in x.items() if k!="dt"} for x in current if x["dt"]==latest]
            outputs.append({"parcel_id":parcel,"semantic_state":state,
              "latest_current_episode":latest_events,
              "historical_nonstandard_codes":sorted(set(x["doccode"] for x in historical if x["doccode"] and x["doccode"]!="BSD")),
              "current_dated_rows":len(current),"historical_dated_rows":len(historical)})

    return {"status":"ok","version":VERSION,
      "mode":"FULL_2082_CURRENT_EVENT_SEMANTICS_READ_ONLY",
      "summary":{"properties_evaluated":len(by),"evidence_rows_consumed":len(rows),
        "current_period_properties":current_props,"semantic_counts":dict(sorted(counts.items())),
        "family_counts":dict(sorted(families.items()))},
      "semantic_test_cases":outputs,
      "policy":{"historical_nonstandard_does_not_define_current_event":True,
        "missing_data_does_not_stop_research":True,"research_may_continue_for_all":True},
      "database_writes":0,
      "guards":{"database_writes":False,"external_calls":False,"schema_introspection":False,
        "investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,
        "overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"INTEGRATE_CHANGE_DETECTION_WITH_MARKET_WIDE_SEMANTICS_AND_EVIDENCE_VALUE"}
