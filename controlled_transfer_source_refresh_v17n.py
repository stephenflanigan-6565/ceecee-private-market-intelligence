#!/usr/bin/env python3
from datetime import datetime, timezone
import json, urllib.parse, urllib.request
from db import connect, execute

VERSION="V17N"
MODE="CONTROLLED_TRANSFER_SOURCE_REFRESH_DELTA_COMPARISON_READ_ONLY"
MARKET="WESTHAMPTON_BEACH_NY"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]
PAGE_SIZE=2000

def _arc_date(ms):
    if ms is None: return None
    try: return datetime.fromtimestamp(float(ms)/1000.0,tz=timezone.utc).date().isoformat()
    except Exception: return None

def _norm(a):
    return {"PARCELID":a.get("PARCELID"),"LIBERPAGE":a.get("LIBERPAGE"),
      "RECORDDATE":_arc_date(a.get("RECORDDATE")),"DOCNUM":a.get("DOCNUM"),
      "DOCCODE":a.get("DOCCODE"),"DOCDATE":_arc_date(a.get("DOCDATE")),
      "ENTRYDATE":_arc_date(a.get("ENTRYDATE")),"TRANSHISSEQ":a.get("TRANSHISSEQ")}

def _canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),default=str)

def _fetch_page(offset):
    params={"where":"PARCELID LIKE '0905%'","outFields":",".join(FIELDS),
      "returnGeometry":"false","orderByFields":"TRANSHISSEQ ASC",
      "resultOffset":str(offset),"resultRecordCount":str(PAGE_SIZE),"f":"json"}
    url=SERVICE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"PrivateMarketIntelligence/17N controlled-refresh"})
    with urllib.request.urlopen(req,timeout=30) as resp:
        payload=json.loads(resp.read().decode("utf-8"))
    if payload.get("error"): raise RuntimeError("County GIS query error: "+str(payload["error"])[:400])
    feats=payload.get("features") or []
    return url,[_norm(f.get("attributes") or {}) for f in feats],bool(payload.get("exceededTransferLimit"))

def _snapshot():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id,source_record_id,payload_json FROM evidence_ledger WHERE market_code=? AND evidence_family='TRANSFER_TITLE'",(MARKET,)).fetchall()
        out=[]
        for r in rows:
            try: out.append(dict(r))
            except Exception: out.append({"parcel_id":r[0],"source_record_id":r[1],"payload_json":r[2]})
        counts={
          "evidence_total":execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0],
          "baseline":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='BASELINE'",(MARKET,)).fetchone()[0],
          "investigate":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(MARKET,)).fetchone()[0]}
        return out,counts
    finally: c.close()

def _old_norm(raw):
    try: p=json.loads(raw)
    except Exception: return None
    aliases={"PARCELID":["PARCELID","parcel_id"],"LIBERPAGE":["LIBERPAGE","liber_page"],
      "RECORDDATE":["RECORDDATE","record_date"],"DOCNUM":["DOCNUM","document_number"],
      "DOCCODE":["DOCCODE","document_code"],"DOCDATE":["DOCDATE","document_date"],
      "ENTRYDATE":["ENTRYDATE","entry_date"],"TRANSHISSEQ":["TRANSHISSEQ","history_sequence"]}
    out={}
    for k,names in aliases.items():
        v=None
        for name in names:
            if name in p: v=p.get(name); break
        if k in ("RECORDDATE","DOCDATE","ENTRYDATE") and isinstance(v,(int,float)): v=_arc_date(v)
        out[k]=v
    return out

def build_controlled_transfer_source_refresh_v17n():
    stored,before=_snapshot()
    stored_map={}
    for r in stored:
        sid=str(r.get("source_record_id") or "")
        if sid: stored_map[(str(r.get("parcel_id")),sid)]=_old_norm(r.get("payload_json"))

    fresh=[]; pages=[]; offset=0
    while True:
        url,recs,more=_fetch_page(offset)
        pages.append({"offset":offset,"records":len(recs),"query_url":url})
        fresh.extend(recs)
        if not recs or not more: break
        offset += len(recs)
        if offset>50000: raise RuntimeError("County refresh safety cap exceeded")

    fresh_map={}
    for r in fresh:
        sid=r.get("TRANSHISSEQ")
        if sid is None: sid=r.get("DOCNUM")
        if sid is not None: fresh_map[(str(r.get("PARCELID")),str(sid))]=r

    new_keys=sorted(set(fresh_map)-set(stored_map))
    missing_keys=sorted(set(stored_map)-set(fresh_map))
    changed=[]; unchanged=0
    for k in set(fresh_map)&set(stored_map):
        if stored_map[k] is not None and _canon(stored_map[k])==_canon(fresh_map[k]): unchanged+=1
        else: changed.append(k)
    changed=sorted(changed)

    _,after=_snapshot()
    return {"status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
      "source_contract":{"service":"Suffolk County GIS TaxParcelTransferHistory","service_url":SERVICE,
        "published_fields":FIELDS,"read_only":True,"party_fields_exposed":False},
      "refresh_summary":{"stored_transfer_rows":len(stored),"fresh_county_rows":len(fresh),
        "fresh_identified_rows":len(fresh_map),"unchanged_source_identities":unchanged,
        "changed_source_identities":len(changed),"new_source_identities":len(new_keys),
        "stored_identities_missing_from_refresh":len(missing_keys),"pages_retrieved":len(pages)},
      "delta_samples":{"new_source_identities":[{"parcel_id":k[0],"source_record_id":k[1]} for k in new_keys[:25]],
        "changed_source_identities":[{"parcel_id":k[0],"source_record_id":k[1]} for k in changed[:25]],
        "missing_from_refresh":[{"parcel_id":k[0],"source_record_id":k[1]} for k in missing_keys[:25]],"sample_limit_each":25},
      "protected_counts_before":before,"protected_counts_after":after,"protected_state_unchanged":before==after,
      "provenance_pages":pages,
      "decision_boundary":{"delta_report_only":True,"persist_new_evidence":False,
        "mark_old_evidence_noncurrent":False,"automatic_investigate_promotion":False,
        "automatic_investigate_demotion":False,
        "next_step_if_clean":"INTERPRET_AND_VALIDATE_REFRESH_DELTAS_BEFORE_ANY_PERSISTENCE"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}

