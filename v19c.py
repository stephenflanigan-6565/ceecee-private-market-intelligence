#!/usr/bin/env python3
import os,json,urllib.parse,urllib.request
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date,datetime,timezone
VERSION="V19B2"
def _norm(v):
    if v is None:return None
    s=str(v).strip()
    return s[:-2] if s.endswith(".0") else s
def _date(v):
    if not v:return None
    try:return date.fromisoformat(str(v)[:10])
    except:return None
def _iso_ms(v):
    if v is None:return None
    try:return datetime.fromtimestamp(float(v)/1000.0,tz=timezone.utc).date().isoformat()
    except:return None
def _fetch(contract,pids):
    allrows=[]; errors=[]
    for i in range(0,len(pids),35):
        batch=pids[i:i+35]
        where="PARCELID IN ("+",".join("'"+p.replace("'","''")+"'" for p in batch)+")"
        params={"where":where,"outFields":",".join(contract["fields"]),"returnGeometry":"false",
                "orderByFields":contract["order_by"],"resultRecordCount":"2000","f":"json"}
        req=urllib.request.Request(contract["url"]+"?"+urllib.parse.urlencode(params),
            headers={"User-Agent":"PrivateMarketIntelligence/19B2 factual-semantics"})
        try:
            with urllib.request.urlopen(req,timeout=25) as resp: payload=json.loads(resp.read().decode())
            if payload.get("error"): errors.append(payload["error"]); continue
            for f in payload.get("features",[]):
                a=f.get("attributes",{})
                allrows.append({"parcel_id":str(a.get("PARCELID")) if a.get("PARCELID") is not None else None,
                  "source_record_id":_norm(a.get("TRANSHISSEQ")),"doccode":a.get("DOCCODE"),
                  "recorddate":_iso_ms(a.get("RECORDDATE")),"docdate":_iso_ms(a.get("DOCDATE")),
                  "entrydate":_iso_ms(a.get("ENTRYDATE")),"liberpage":a.get("LIBERPAGE"),
                  "docnum":_norm(a.get("DOCNUM"))})
        except Exception as e: errors.append({"type":type(e).__name__,"message":str(e)[:300]})
    return allrows,errors

import os,json
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date
VERSION="V19C"

def build_v19c():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19c_donor.json").read_text())
    cutoff=date.fromisoformat(d["current_cutoff"]); market=d["market_code"]
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,source_record_id,event_date,quality_state
                       FROM evidence_ledger WHERE market_code=%s AND is_current=1
                       AND evidence_family='TRANSFER_TITLE' ORDER BY parcel_id,event_date,source_record_id""",(market,))
        ledger=cur.fetchall()
        cur.execute("""SELECT COUNT(DISTINCT parcel_id) FROM evidence_ledger
                       WHERE market_code=%s AND is_current=1""",(market,))
        universe=int(cur.fetchone()[0])
    finally: conn.close()

    mem=defaultdict(dict)
    current_pids=set()
    for pid,sid,ed,qs in ledger:
        sid=_norm(sid); dt=_date(ed)
        mem[pid][sid]={"event_date":str(ed) if ed else None,"quality_state":qs}
        if dt and dt>=cutoff: current_pids.add(pid)

    source,errors=_fetch(d["source_contract"],sorted(current_pids))
    bysrc=defaultdict(list)
    for r in source:
        if r.get("parcel_id"): bysrc[r["parcel_id"]].append(r)

    changes=[]; unchanged=0; new_ids=0; metadata_completion=0
    for pid in sorted(current_pids):
        known=mem.get(pid,{})
        for r in bysrc.get(pid,[]):
            sid=r.get("source_record_id")
            # Only treat source observations with a current factual date as current source activity.
            dates=[_date(r.get(k)) for k in ("recorddate","docdate","entrydate")]
            dates=[x for x in dates if x]
            if not dates or max(dates)<cutoff: continue
            if sid not in known:
                new_ids+=1
                changes.append({"parcel_id":pid,"change_type":"NEW_SOURCE_IDENTITY",
                    "source_record_id":sid,"doccode":r.get("doccode"),"recorddate":r.get("recorddate"),
                    "docdate":r.get("docdate"),"entrydate":r.get("entrydate"),"liberpage":r.get("liberpage")})
            else:
                m=known[sid]
                # Ledger's preserved top-level event_date can establish chronology but cannot prove
                # whether source metadata fields were stored. Flag completion only when source has
                # recording metadata and the stored row is already known partial by quality state.
                if str(m.get("quality_state","")).upper()!="VALID" and (r.get("recorddate") or r.get("liberpage")):
                    metadata_completion+=1
                    changes.append({"parcel_id":pid,"change_type":"AUTHORITATIVE_METADATA_COMPLETION",
                        "source_record_id":sid,"doccode":r.get("doccode"),"recorddate":r.get("recorddate"),
                        "docdate":r.get("docdate"),"entrydate":r.get("entrydate"),"liberpage":r.get("liberpage"),
                        "prior_quality_state":m.get("quality_state")})
                else: unchanged+=1

    parcels=sorted(set(x["parcel_id"] for x in changes))
    types=Counter(x["change_type"] for x in changes)
    return {"status":"ok","version":VERSION,"mode":"VERIFIED_CURRENT_EVENT_SEMANTICS_PLUS_CHANGE_DETECTION_READ_ONLY",
      "summary":{"properties_evaluated_full_universe":universe,"transfer_rows_in_memory":len(ledger),
        "current_period_properties_checked":len(current_pids),"authoritative_rows_returned":len(source),
        "current_source_observations_compared":unchanged+len(changes),
        "unchanged_current_source_observations":unchanged,
        "genuine_change_observations":len(changes),"properties_with_genuine_change":len(parcels),
        "change_type_counts":dict(sorted(types.items())),"source_batch_errors":len(errors)},
      "genuine_changes":changes[:100],"genuine_change_parcel_ids":parcels,
      "source_errors":errors,
      "change_detection_rule":"TRANSHISSEQ identity first. Static historical context is not a change. Current authoritative identities absent from persistent memory are new factual observations.",
      "policy":{"historical_nonstandard_does_not_define_current_event":True,
        "static_history_does_not_manufacture_change":True,"missing_data_does_not_stop_research":True,
        "research_may_continue_for_all":True},
      "database_writes":0,"guards":{"database_writes":False,"schema_introspection":False,
        "investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,
        "overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"INTEGRATE_CHANGE_DETECTION_WITH_MARKET_WIDE_SEMANTICS_AND_EVIDENCE_VALUE"}
