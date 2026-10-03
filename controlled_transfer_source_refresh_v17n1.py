#!/usr/bin/env python3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json, urllib.parse, urllib.request
from db import connect, execute

VERSION="V17N1"
MODE="CONTROLLED_TRANSFER_SOURCE_REFRESH_CANONICAL_DELTA_REPAIR"
MARKET="WESTHAMPTON_BEACH_NY"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]
PAGE_SIZE=2000

def _arc_date(v):
    if v is None: return None
    try: return datetime.fromtimestamp(float(v)/1000.0,tz=timezone.utc).date().isoformat()
    except Exception: return str(v)[:10] if isinstance(v,str) and len(v)>=10 else v

def _sid(v):
    if v is None: return None
    s=str(v).strip()
    if not s: return None
    try:
        d=Decimal(s)
        if d==d.to_integral(): return str(d.quantize(Decimal("1")))
    except (InvalidOperation,ValueError): pass
    return s

def _text(v):
    if v is None: return None
    s=str(v).strip()
    return s if s else None

def _fresh_norm(a):
    return {"PARCELID":_text(a.get("PARCELID")),"LIBERPAGE":_text(a.get("LIBERPAGE")),
      "RECORDDATE":_arc_date(a.get("RECORDDATE")),"DOCNUM":_text(a.get("DOCNUM")),
      "DOCCODE":_text(a.get("DOCCODE")),"DOCDATE":_arc_date(a.get("DOCDATE")),
      "ENTRYDATE":_arc_date(a.get("ENTRYDATE")),"TRANSHISSEQ":_sid(a.get("TRANSHISSEQ"))}

def _old_norm(raw):
    try: p=json.loads(raw)
    except Exception: return None
    def pick(*names):
        for n in names:
            if n in p: return p.get(n)
        return None
    return {"PARCELID":_text(pick("PARCELID","parcel_id")),
      "LIBERPAGE":_text(pick("LIBERPAGE","liber_page")),
      "RECORDDATE":_arc_date(pick("RECORDDATE","record_date")),
      "DOCNUM":_text(pick("DOCNUM","document_number")),
      "DOCCODE":_text(pick("DOCCODE","document_code")),
      "DOCDATE":_arc_date(pick("DOCDATE","document_date")),
      "ENTRYDATE":_arc_date(pick("ENTRYDATE","entry_date")),
      "TRANSHISSEQ":_sid(pick("TRANSHISSEQ","history_sequence"))}

def _canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),default=str)

def _fetch_page(offset):
    params={"where":"PARCELID LIKE '0905%'","outFields":",".join(FIELDS),
      "returnGeometry":"false","orderByFields":"TRANSHISSEQ ASC","resultOffset":str(offset),
      "resultRecordCount":str(PAGE_SIZE),"f":"json"}
    url=SERVICE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"PrivateMarketIntelligence/17N1 canonical-delta"})
    with urllib.request.urlopen(req,timeout=30) as resp: payload=json.loads(resp.read().decode("utf-8"))
    if payload.get("error"): raise RuntimeError("County GIS query error: "+str(payload["error"])[:400])
    feats=payload.get("features") or []
    return url,[_fresh_norm(f.get("attributes") or {}) for f in feats],bool(payload.get("exceededTransferLimit"))

def _snapshot():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id,source_record_id,payload_json FROM evidence_ledger WHERE market_code=? AND evidence_family='TRANSFER_TITLE'",(MARKET,)).fetchall()
        out=[]
        for r in rows:
            try: out.append(dict(r))
            except Exception: out.append({"parcel_id":r[0],"source_record_id":r[1],"payload_json":r[2]})
        counts={"evidence_total":execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0],
          "baseline":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='BASELINE'",(MARKET,)).fetchone()[0],
          "investigate":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(MARKET,)).fetchone()[0]}
        return out,counts
    finally: c.close()

def build_controlled_transfer_source_refresh_v17n1():
    stored,before=_snapshot(); stored_map={}
    for r in stored:
        old=_old_norm(r.get("payload_json"))
        sid=_sid(r.get("source_record_id"))
        pid=_text(r.get("parcel_id"))
        if sid: stored_map[(pid,sid)]=old

    fresh=[]; pages=[]; offset=0
    while True:
        url,recs,more=_fetch_page(offset); fresh.extend(recs)
        pages.append({"offset":offset,"records":len(recs),"query_url":url})
        if not recs or not more: break
        offset+=len(recs)
        if offset>50000: raise RuntimeError("County refresh safety cap exceeded")

    fresh_map={}
    for r in fresh:
        sid=_sid(r.get("TRANSHISSEQ")) or _sid(r.get("DOCNUM"))
        if sid: fresh_map[(_text(r.get("PARCELID")),sid)]=r

    new_keys=sorted(set(fresh_map)-set(stored_map))
    missing=sorted(set(stored_map)-set(fresh_map))
    changed=[]; unchanged=0
    for k in set(fresh_map)&set(stored_map):
        if stored_map[k] is not None and _canon(stored_map[k])==_canon(fresh_map[k]): unchanged+=1
        else: changed.append(k)
    changed=sorted(changed)
    _,after=_snapshot()

    return {"status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
      "repair":{"rejected_version":"V17N","identity_normalization":"NUMERIC_SOURCE_IDS_CANONICALIZED_WITHOUT_TRAILING_DECIMAL",
        "payload_comparison":"ONLY_EIGHT_PROVEN_AUTHORITATIVE_GIS_FIELDS"},
      "refresh_summary":{"stored_transfer_rows":len(stored),"fresh_county_rows":len(fresh),
        "stored_identified_rows":len(stored_map),"fresh_identified_rows":len(fresh_map),
        "unchanged_source_identities":unchanged,"changed_source_identities":len(changed),
        "new_source_identities":len(new_keys),"stored_identities_missing_from_refresh":len(missing),
        "pages_retrieved":len(pages)},
      "delta_samples":{"new_source_identities":[{"parcel_id":k[0],"source_record_id":k[1]} for k in new_keys[:25]],
        "changed_source_identities":[{"parcel_id":k[0],"source_record_id":k[1]} for k in changed[:25]],
        "missing_from_refresh":[{"parcel_id":k[0],"source_record_id":k[1]} for k in missing[:25]],"sample_limit_each":25},
      "protected_counts_before":before,"protected_counts_after":after,"protected_state_unchanged":before==after,
      "provenance_pages":pages,
      "decision_boundary":{"delta_report_only":True,"persist_new_evidence":False,
        "automatic_investigate_promotion":False,"automatic_investigate_demotion":False,
        "next_step_if_clean":"VALIDATE_GENUINE_REFRESH_DELTAS_BEFORE_PERSISTENCE"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}

