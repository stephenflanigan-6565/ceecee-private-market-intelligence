#!/usr/bin/env python3
"""V17P — Eight-delta event semantics and research-question gate.
Read-only. Separates new instruments from authoritative completion/correction
of already-known source identities. No persistence or INVESTIGATE authority.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json, urllib.parse, urllib.request
from db import connect, execute

VERSION="V17P"
MODE="EIGHT_DELTA_EVENT_SEMANTICS_RESEARCH_QUESTION_GATE_READ_ONLY"
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
    req=urllib.request.Request(url,headers={"User-Agent":"PrivateMarketIntelligence/17P event-semantics"})
    with urllib.request.urlopen(req,timeout=30) as resp: payload=json.loads(resp.read().decode("utf-8"))
    if payload.get("error"): raise RuntimeError("County GIS query error: "+str(payload["error"])[:400])
    fs=payload.get("features") or []
    return [_norm(f.get("attributes") or {}) for f in fs],bool(payload.get("exceededTransferLimit"))

def _snapshot():
    c=connect()
    try:
        rr=execute(c,"SELECT parcel_id,source_record_id,payload_json,first_seen_at FROM evidence_ledger WHERE market_code=? AND evidence_family='TRANSFER_TITLE'",(MARKET,)).fetchall()
        rows=[]
        for r in rr:
            try: rows.append(dict(r))
            except Exception: rows.append({"parcel_id":r[0],"source_record_id":r[1],"payload_json":r[2],"first_seen_at":r[3]})
        mm=execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=?",(MARKET,)).fetchall()
        members=set()
        for r in mm:
            try: members.add(str(r["parcel_id"]))
            except Exception: members.add(str(r[0]))
        counts={"evidence_total":execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(MARKET,)).fetchone()[0],
          "baseline":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='BASELINE'",(MARKET,)).fetchone()[0],
          "investigate":execute(c,"SELECT COUNT(*) FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'",(MARKET,)).fetchone()[0]}
        return rows,members,counts
    finally: c.close()

def build_eight_delta_event_semantics_v17p():
    stored,members,before=_snapshot()
    smap={}; first=[]
    for r in stored:
        pid=_txt(r.get("parcel_id")); sid=_sid(r.get("source_record_id"))
        if sid: smap[(pid,sid)]=_old(r.get("payload_json"))
        if r.get("first_seen_at"): first.append(str(r.get("first_seen_at")))
    baseline=min(first)[:10] if first else None

    fresh=[]; off=0
    while True:
        recs,more=_fetch(off); fresh.extend(recs)
        if not recs or not more: break
        off += len(recs)
        if off>50000: raise RuntimeError("County refresh safety cap exceeded")
    fmap={}
    for r in fresh:
        sid=_sid(r.get("TRANSHISSEQ")) or _sid(r.get("DOCNUM"))
        if sid: fmap[(_txt(r.get("PARCELID")),sid)]=r

    new_post=[]
    for k in sorted(set(fmap)-set(smap)):
        r=fmap[k]; pid=k[0]
        if pid in members and baseline and ((r.get("RECORDDATE") and r["RECORDDATE"]>=baseline) or
                                            (r.get("ENTRYDATE") and r["ENTRYDATE"]>=baseline)):
            new_post.append((k,r))

    enrich=[]
    for k in sorted(set(fmap)&set(smap)):
        old=smap[k]; new=fmap[k]
        if old is None: continue
        diffs={f:{"stored":old.get(f),"fresh":new.get(f)} for f in FIELDS if old.get(f)!=new.get(f)}
        if diffs: enrich.append((k,old,new,diffs))

    new_packets=[]
    for k,r in new_post:
        missing=[f for f in ("RECORDDATE","LIBERPAGE") if not r.get(f)]
        questions=[]
        if missing:
            questions.append("WAIT_FOR_OR_VERIFY_COUNTY_COMPLETION_OF_"+ "_AND_".join(missing))
        # A genuinely new source identity is a new factual event, but document code alone
        # is not interpreted as seller intent or disposition motive.
        questions.append("COMPARE_NEW_INSTRUMENT_WITH_PRIOR_PROPERTY_TITLE_SEQUENCE")
        new_packets.append({"parcel_id":k[0],"source_record_id":k[1],
          "event_semantics":"NEW_AUTHORITATIVE_SOURCE_IDENTITY",
          "document_code":r.get("DOCCODE"),"record_date":r.get("RECORDDATE"),
          "document_date":r.get("DOCDATE"),"entry_date":r.get("ENTRYDATE"),
          "liber_page":r.get("LIBERPAGE"),"metadata_completion_pending":bool(missing),
          "missing_authoritative_fields":missing,"research_questions":questions})

    enrichment_packets=[]
    for k,old,new,diffs in enrich:
        completion_only=all(v.get("stored") is None and v.get("fresh") is not None for v in diffs.values())
        questions=[]
        if completion_only:
            questions.append("RE_EVALUATE_EXISTING_INSTRUMENT_WITH_NEWLY_COMPLETED_AUTHORITATIVE_METADATA")
        else:
            questions.append("VALIDATE_AUTHORITATIVE_CORRECTION_OR_CONTRADICTION")
        enrichment_packets.append({"parcel_id":k[0],"source_record_id":k[1],
          "event_semantics":"EXISTING_SOURCE_IDENTITY_METADATA_COMPLETION" if completion_only else "EXISTING_SOURCE_IDENTITY_AUTHORITATIVE_CHANGE",
          "document_code":new.get("DOCCODE"),"field_differences":diffs,
          "creates_second_event":False,"research_questions":questions})

    _,_,after=_snapshot()
    return {"status":"ok","version":VERSION,"mode":MODE,"market_code":MARKET,
      "baseline_memory_date":baseline,
      "summary":{"new_post_baseline_source_identities":len(new_packets),
        "existing_identities_with_authoritative_field_changes":len(enrichment_packets),
        "total_deltas_routed":len(new_packets)+len(enrichment_packets),
        "new_events_requiring_sequence_comparison":len(new_packets),
        "existing_events_requiring_metadata_reevaluation":len(enrichment_packets)},
      "new_event_packets":new_packets,
      "existing_event_enrichment_packets":enrichment_packets,
      "semantic_rules":{"new_source_identity_can_be_new_factual_event":True,
        "same_source_identity_with_completed_fields_creates_second_event":False,
        "document_code_alone_implies_seller_intent":False,
        "entrydate_substitutes_for_recorddate":False,
        "missing_recorddate_or_liberpage_is_preserved":True},
      "protected_counts_before":before,"protected_counts_after":after,"protected_state_unchanged":before==after,
      "decision_boundary":{"persistence_authorized":False,"investigate_promotion_authorized":False,
        "research_question_creation_only":True,
        "next_step_if_clean":"BUILD_DELTA_SPECIFIC_FACTUAL_RESEARCH_QUESTIONS_AND_REEVALUATION_PACKETS"},
      "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False}}

