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

def build_v19b2():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19b2_donor.json").read_text())
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
    by=defaultdict(list)
    for pid,sid,ed,qs in ledger:
        by[pid].append({"source_record_id":_norm(sid),"event_date":str(ed) if ed else None,
                        "dt":_date(ed),"quality_state":qs})
    current_pids=sorted(pid for pid,rows in by.items() if any(x["dt"] and x["dt"]>=cutoff for x in rows))
    source,errors=_fetch(d["source_contract"],current_pids)
    smap={(r["parcel_id"],r["source_record_id"]):r for r in source if r["parcel_id"] and r["source_record_id"]}
    source_by=defaultdict(list)
    for r in source: source_by[r["parcel_id"]].append(r)
    counts=Counter(); cases=[]; matched=0; unresolved=0
    checks=set(d["known_semantic_checks"])
    for pid in current_pids:
        current=[x for x in by[pid] if x["dt"] and x["dt"]>=cutoff]
        latest=max(x["dt"] for x in current)
        episode=[x for x in current if x["dt"]==latest]
        resolved=[]
        for x in episode:
            sr=smap.get((pid,x["source_record_id"]))
            if sr: matched+=1
            else: unresolved+=1
            resolved.append({**{k:v for k,v in x.items() if k!="dt"},
                             "doccode":sr.get("doccode") if sr else None,
                             "recorddate":sr.get("recorddate") if sr else None,
                             "docdate":sr.get("docdate") if sr else None,
                             "entrydate":sr.get("entrydate") if sr else None,
                             "liberpage":sr.get("liberpage") if sr else None,
                             "authoritative_identity_matched":bool(sr)})
        codes=[x["doccode"] for x in resolved if x["doccode"]]
        incomplete=any(not x["authoritative_identity_matched"] or x["recorddate"] is None or x["liberpage"] is None for x in resolved)
        hist_nonstd=sorted(set(r["doccode"] for r in source_by[pid]
            if r.get("doccode") and r["doccode"]!="BSD"
            and max([q for q in [r.get("recorddate"),r.get("docdate"),r.get("entrydate")] if q] or ["9999-12-31"]) < d["current_cutoff"]))
        if len(resolved)>1: state="CURRENT_MULTI_DOCUMENT_SAME_DAY_EPISODE"
        elif incomplete: state="CURRENT_EVENT_METADATA_INCOMPLETE"
        elif any(c!="BSD" for c in codes): state="CURRENT_NON_STANDARD_EVENT"
        elif hist_nonstd: state="CURRENT_CONVEYANCE_WITH_HISTORICAL_NONSTANDARD_BACKGROUND"
        else: state="CURRENT_STANDARD_CONVEYANCE_CONTEXT"
        counts[state]+=1
        if pid in checks:
            cases.append({"parcel_id":pid,"semantic_state":state,"latest_current_episode":resolved,
                          "historical_nonstandard_codes":hist_nonstd})
    # Include known checks that are outside the current-period lane, without source calls for them.
    for pid in sorted(checks-set(current_pids)):
        cases.append({"parcel_id":pid,"semantic_state":"NO_CURRENT_TRANSFER_EPISODE",
                      "latest_current_episode":[],"historical_nonstandard_codes":[]})
    return {"status":"ok","version":VERSION,"mode":"CURRENT_126_AUTHORITATIVE_DOCUMENT_SEMANTIC_REPAIR_READ_ONLY",
      "summary":{"properties_evaluated_full_universe":universe,"transfer_rows_in_memory":len(ledger),
        "current_period_properties":len(current_pids),"authoritative_rows_returned":len(source),
        "latest_episode_identities_matched":matched,"latest_episode_identities_unresolved":unresolved,
        "source_batch_errors":len(errors),"semantic_counts":dict(sorted(counts.items()))},
      "source_errors":errors,"semantic_test_cases":sorted(cases,key=lambda x:x["parcel_id"]),
      "identity_rule":"TRANSHISSEQ is the Suffolk transfer-history identity; DOCNUM is metadata only.",
      "policy":{"historical_nonstandard_does_not_define_current_event":True,
                "missing_data_does_not_stop_research":True,"research_may_continue_for_all":True},
      "database_writes":0,"guards":{"database_writes":False,"schema_introspection":False,
        "investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,
        "overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_verified":"LOCK_CURRENT_EVENT_SEMANTICS_AND_INTEGRATE_WITH_CHANGE_DETECTION"}
