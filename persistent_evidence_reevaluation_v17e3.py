#!/usr/bin/env python3
from db import connect, execute
from evidence_resolution_date_semantics_v17c import build_evidence_resolution_date_semantics_v17c
from authoritative_research_evidence_memory_v17d import _stable, _key, PILOT

VERSION="V17E3"
MODE="PERSISTENT_EVIDENCE_REEVALUATION_CONTAINED"

def _expected(src):
    out=[]
    for research in src.get("resolved_research") or []:
        pid=str(research.get("parcel_id"))
        for row in research.get("authoritative_evidence") or []:
            payload=_stable({"research_request_id":research.get("research_request_id"),
                "resolution_state":research.get("resolution_state"),
                "date_semantics":research.get("date_semantics"),"county_record":row})
            seq=row.get("history_sequence")
            out.append((pid,"COUNTY_TRANSFER_INSTRUMENT_METADATA",str(seq or ""),
                _key(pid,"COUNTY_TRANSFER_INSTRUMENT_METADATA",seq,payload)))
        payload=_stable({"research_request_id":research.get("research_request_id"),
            "evidence_target":research.get("evidence_target"),
            "resolution_state":research.get("resolution_state"),
            "resolved_facts":research.get("resolved_facts") or [],
            "remaining_unknowns":research.get("remaining_unknowns") or [],
            "date_semantics":research.get("date_semantics")})
        rid=research.get("research_request_id")
        out.append((pid,"RESEARCH_QUESTION_RESOLUTION",str(rid or ""),
            _key(pid,"RESEARCH_QUESTION_RESOLUTION",rid,payload)))
    return out

def build_persistent_evidence_reevaluation_v17e3():
    src=build_evidence_resolution_date_semantics_v17c()
    if src.get("status")!="ok":
        return {"status":"failed","version":VERSION,"error":"V17C prerequisite failed"}
    expected=_expected(src)
    c=connect()
    try:
        v16_before=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(PILOT,)).fetchone()[0]
        rows=execute(c,"SELECT evidence_key,parcel_id,evidence_type,source_record_id FROM authoritative_research_evidence WHERE market_code=? AND is_current=1",(PILOT,)).fetchall()
        persisted_keys=set()
        logical={}
        for r in rows:
            k=str(r[0]); pid=str(r[1]); et=str(r[2]); sid=str(r[3] or "")
            persisted_keys.add(k); logical[(pid,et,sid)]=k
        confirmed=0; genuinely_new=[]; changed=[]; expected_keys=set()
        for pid,etype,sid,key in expected:
            expected_keys.add(key)
            if key in persisted_keys:
                confirmed += 1
            elif (pid,etype,sid) in logical:
                changed.append({"parcel_id":pid,"evidence_type":etype,"source_record_id":sid,
                    "classification":"CHANGED_OR_CONTRADICTORY_PAYLOAD"})
            else:
                genuinely_new.append({"parcel_id":pid,"evidence_type":etype,"source_record_id":sid})
        stale_count=sum(1 for k in persisted_keys if k not in expected_keys)
        unresolved=[]
        for research in src.get("resolved_research") or []:
            for q in research.get("remaining_unknowns") or []:
                unresolved.append({"parcel_id":str(research.get("parcel_id")),
                    "research_request_id":research.get("research_request_id"),"unknown":q})
        v16_after=execute(c,"SELECT COUNT(*) FROM evidence_ledger WHERE market_code=?",(PILOT,)).fetchone()[0]
        v17d_total=execute(c,"SELECT COUNT(*) FROM authoritative_research_evidence WHERE market_code=?",(PILOT,)).fetchone()[0]
    finally:
        c.close()
    if v16_after != v16_before:
        raise RuntimeError("Protected V16A evidence ledger count changed during read-only V17E3")
    return {"status":"ok","version":VERSION,"mode":MODE,"market_code":PILOT,
        "source_contract":{"version":src.get("version"),"current_observations":len(expected)},
        "memory_contract":{"version":"V17D","persisted_current_rows":len(rows)},
        "reevaluation":{"confirmed_unchanged":confirmed,"genuinely_new":len(genuinely_new),
            "changed_or_contradictory":len(changed),"persisted_not_in_current_snapshot":stale_count,
            "remaining_unknowns":len(unresolved),"new_items":genuinely_new,
            "changed_or_contradictory_items":changed,"unresolved_questions":unresolved},
        "decision":{"further_research_warranted":bool(genuinely_new or changed or unresolved),
            "reason":"UNRESOLVED_FACTUAL_QUESTIONS_REMAIN" if unresolved else
            ("NEW_OR_CHANGED_AUTHORITATIVE_EVIDENCE" if genuinely_new or changed else "NO_NEW_RESEARCH_REQUIRED")},
        "protected_counts":{"v16a_evidence_ledger_before":v16_before,
            "v16a_evidence_ledger_after":v16_after,"v17d_authoritative_memory_after":v17d_total},
        "guards":{"database_writes":False,"v16a_evidence_ledger_modified":False,
            "v17d_authoritative_memory_modified":False,"investigate_state_touched":False,
            "new_candidate_created":False,"seller_intent_inferred":False,"seller_scoring":False,
            "contact_authorized":False,"outreach_touched":False}}
