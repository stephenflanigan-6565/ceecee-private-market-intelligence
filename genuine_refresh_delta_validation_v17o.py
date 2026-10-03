#!/usr/bin/env python3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json, urllib.parse, urllib.request
from db import connect, execute

VERSION="V17O"
MODE="GENUINE_REFRESH_DELTA_VALIDATION_READ_ONLY"
MARKET="WESTHAMPTON_BEACH_NY"
SERVICE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/MapServer/0/query"
FIELDS=["PARCELID","LIBERPAGE","RECORDDATE","DOCNUM","DOCCODE","DOCDATE","ENTRYDATE","TRANSHISSEQ"]
PAGE_SIZE=2000

def _date(v):
    if v is None: return None
    if isinstance(v,str):
        s=v.strip()
        if len(s)>=10 and s[4:5]=="-" and s[7:8]=="-": return s[:10]
    try: return datetime.fromtimestamp(float(v)/1000.0,tz=timezone.utc).date().isoformat()
    except Exception: return None

def _sid(v):
    if v is None: return None
    s=str(v).strip()
    if not s: return None
    try:
        d=Decimal(s)
        if d==d.to_integral(): return str(d.quantize(Decimal("1")))
    except (InvalidOperation,ValueError): pass
    return s

def _txt(v):
    if v is None: return None
    s=str(v).strip()
    return s if s else None

def _norm(a):
    return {"PARCELID":_txt(a.get("PARCELID")),"LIBERPAGE":_txt(a.get("LIBERPAGE")),
      "RECORDDATE":_date(a.get("RECORDDATE")),"DOCNUM":_txt(a.get("DOCNUM")),
      "DOCCODE":_txt(a.get("DOCCODE")),"DOCDATE":_date(a.get("DOCDATE")),
      "ENTRYDATE":_date(a.get("ENTRYDATE")),"TRANSHISSEQ":_sid(a.get("TRANSHISSEQ"))}

def _old(raw):
    try: p=json.loads(raw)
    except Exception: return None
    def pick(*ns):
        for n in ns:
            if n in p: return p.get(n)
        return None
    return _norm({"PARCELID":pick("PARCELID","parcel_id"),"LIBERPAGE":pick("LIBERPAGE","liber_page"),
      "RECORDDATE":pick("RECORDDATE","record_date"),"DOCNUM":pick("DOCNUM","document_number"),
      "DOCCODE":pick("DOCCODE","document_code"),"DOCDATE":pick("DOCDATE","document_date"),
      "ENTRYDATE":pick("ENTRYDATE","entry_date"),"TRANSHISSEQ":pick("TRANSHISSEQ","history_sequence")})

def _fetch(offset):
    params={"where":"PARCELID LIKE '0905%'","outFields":",".join(FIELDS),"returnGeometry":"false",
      "orderByFields":"TRANSHISSEQ ASC","resultOffset":str(offset),"resultRecordCount":str(PAGE_SIZE),"f":"json"}
    url=SERVICE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"PrivateMarketIntelligence/17O delta-validation"})
    with urllib.request.urlopen(req,timeout=30) as resp: payload=json.loads(resp.read().decode("utf-8"))
    if payload.get("error"): raise RuntimeError("County GIS query error: "+str(payload["error"])[:400])
    fs=payload.get("features") or []
    return [_norm(f.get("attributes") or {}) for f in fs],bool(payload.get("exceededTransferLimit"))

def _db_snapshot():
    c=connect()
    try:
        rr=execute(c,"SELECT parcel_id,source_record_id,payload_json,first_seen_at FROM evidence_ledger WHERE market_code=? AND evidence_family='TRANSFER_TITLE'",(MARKET,)).fetchall()
        stored=[]
        for r in rr:
            try: stored.append(dict(r))
            except Exception: stored.append({"parcel_id":r[0],"source_record_id":r[1],"payload_json":r[2],"first_seen_at":r[3]})
        members=execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=?",(MARKET,)).fetchall()
        mids=set()
        for r in members:
            try: mids.add(str(r["parcel_id"]))
            except Exception: mids.add(str(r[0]))
        counts={"evidence_total":execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0],
          "baseline":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='BASELINE'",(MARKET,)).fetchone()[0],
          "investigate":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(MARKET,)).fetchone()[0]}
        return stored,mids,counts
    finally: c.close()

def build_genuine_refresh_delta_validation_v17o():
    stored,members,before=_db_snapshot()
    smap={}; first_seen=[]
    for r in stored:
        k=(_txt(r.get("parcel_id")),_sid(r.get("source_record_id")))
        if k[1]: smap[k]=_old(r.get("payload_json"))
        if r.get("first_seen_at"): first_seen.append(str(r.get("first_seen_at")))
    baseline_memory_date=min(first_seen)[:10] if first_seen else None

    fresh=[]; off=0
    while True:
        recs,more=_fetch(off); fresh.extend(recs)
        if not recs or not more: break
        off+=len(recs)
        if off>50000: raise RuntimeError("County refresh safety cap exceeded")
    fmap={}
    for r in fresh:
        sid=_sid(r.get("TRANSHISSEQ")) or _sid(r.get("DOCNUM"))
        if sid: fmap[(_txt(r.get("PARCELID")),sid)]=r

    newkeys=sorted(set(fmap)-set(smap)); common=set(fmap)&set(smap)
    changed=[]
    for k in common:
        old=smap[k]; new=fmap[k]
        diffs={}
        if old is None: diffs["stored_payload"]="UNREADABLE"
        else:
            for f in FIELDS:
                if old.get(f)!=new.get(f): diffs[f]={"stored":old.get(f),"fresh":new.get(f)}
        if diffs: changed.append((k,diffs,new))

    classes={"OUTSIDE_RESIDENTIAL_WORKING_UNIVERSE":0,"POST_BASELINE_SOURCE_ACTIVITY":0,
      "HISTORICAL_OR_PREBASELINE_BACKFILL":0,"DATE_INSUFFICIENT_TO_CLASSIFY":0}
    samples={k:[] for k in classes}
    for k in newkeys:
        r=fmap[k]; pid=k[0]; rd=r.get("RECORDDATE"); ed=r.get("ENTRYDATE")
        if pid not in members: cls="OUTSIDE_RESIDENTIAL_WORKING_UNIVERSE"
        elif baseline_memory_date and ((rd and rd>=baseline_memory_date) or (ed and ed>=baseline_memory_date)):
            cls="POST_BASELINE_SOURCE_ACTIVITY"
        elif rd or ed: cls="HISTORICAL_OR_PREBASELINE_BACKFILL"
        else: cls="DATE_INSUFFICIENT_TO_CLASSIFY"
        classes[cls]+=1
        if len(samples[cls])<15:
            samples[cls].append({"parcel_id":pid,"source_record_id":k[1],"record_date":rd,
              "entry_date":ed,"document_code":r.get("DOCCODE"),"liber_page":r.get("LIBERPAGE")})

    change_fields={}
    changed_samples=[]
    for k,diffs,new in sorted(changed,key=lambda x:x[0]):
        for f in diffs: change_fields[f]=change_fields.get(f,0)+1
        if len(changed_samples)<25:
            changed_samples.append({"parcel_id":k[0],"source_record_id":k[1],
              "field_differences":diffs,"fresh_record_date":new.get("RECORDDATE"),
              "fresh_entry_date":new.get("ENTRYDATE"),"document_code":new.get("DOCCODE")})

    _,_,after=_db_snapshot()
    return {"status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
      "validation_basis":{"baseline_memory_first_seen_date":baseline_memory_date,
        "residential_membership_count":len(members),
        "classification_is_factual_triage_not_seller_scoring":True,
        "post_baseline_rule":"residential member AND RECORDDATE or ENTRYDATE on/after baseline memory date"},
      "delta_validation":{"fresh_rows":len(fresh),"stored_rows":len(stored),
        "apparent_new_identities":len(newkeys),"changed_identities":len(changed),
        "new_identity_classification":classes,"changed_fields":change_fields},
      "samples":{"new_by_class":samples,"changed_identity_details":changed_samples},
      "protected_counts_before":before,"protected_counts_after":after,"protected_state_unchanged":before==after,
      "decision_boundary":{"persistence_authorized":False,"investigate_promotion_authorized":False,
        "historical_backfill_is_not_automatically_new_market_activity":True,
        "outside_working_universe_is_not_candidate_creation":True,
        "next_step_if_clean":"ISOLATE_AND_VALIDATE_POST_BASELINE_SOURCE_ACTIVITY_AND_AUTHORITATIVE_CORRECTIONS"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}

