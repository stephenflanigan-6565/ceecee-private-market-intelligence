#!/usr/bin/env python3
"""V17C — Evidence Resolution & Date-Semantics Repair.

Read-only resolution layer over V17B.
Preserves RECORDDATE, DOCDATE, and ENTRYDATE as distinct facts.
Never substitutes one date type for another and never silently repairs source history.
"""
from datetime import datetime, timezone
from suffolk_county_transfer_history_v17b import build_suffolk_county_transfer_history_retrieval_v17b

VERSION = "V17C"
MODE = "READ_ONLY_EVIDENCE_RESOLUTION_AND_DATE_SEMANTICS"

def _resolve(result):
    target = result.get("evidence_target")
    rows = result.get("county_records_in_window") or []
    parcel = result.get("parcel_id")
    rrid = result.get("research_request_id")

    out = {
        "research_request_id": rrid,
        "parcel_id": parcel,
        "evidence_target": target,
        "resolution_state": "UNRESOLVED",
        "resolved_facts": [],
        "remaining_unknowns": [],
        "authoritative_evidence": rows,
        "date_semantics": {
            "record_date": "COUNTY_RECORDING_DATE",
            "document_date": "INSTRUMENT_STATED_DATE",
            "entry_date": "COUNTY_SYSTEM_ENTRY_DATE",
            "dates_interchangeable": False
        }
    }

    if target == "SAME_DAY_INSTRUMENT_IDENTITY":
        wrd = [r for r in rows if r.get("document_code") == "WRD"]
        identities = {(r.get("liber_page"), r.get("history_sequence")) for r in wrd
                      if r.get("liber_page") is not None}
        if len(wrd) >= 2 and len(identities) >= 2:
            out["resolution_state"] = "RESOLVED_DISTINCT_RECORDED_INSTRUMENTS"
            out["resolved_facts"] = [
                "SAME_DAY_WRD_RECORDS_ARE_DISTINCT_RECORDED_INSTRUMENTS",
                "DISTINCT_LIBER_PAGE_IDENTITIES_PRESENT"
            ]
        else:
            out["remaining_unknowns"].append("DISTINCT_INSTRUMENT_IDENTITY_NOT_PROVEN")

    elif target == "RECORDED_INSTRUMENT_DETAIL":
        codes = {r.get("document_code") for r in rows}
        identified = [r for r in rows if r.get("liber_page") and r.get("record_date")]
        if identified:
            out["resolved_facts"].append("AT_LEAST_ONE_TARGET_INSTRUMENT_HAS_AUTHORITATIVE_RECORDING_IDENTITY")
        if "EXD" in codes and "BSD" in codes:
            both = [r for r in rows if r.get("document_code") in ("EXD","BSD")]
            if all(r.get("liber_page") and r.get("record_date") for r in both):
                out["resolution_state"] = "PARTIALLY_RESOLVED_INSTRUMENT_IDENTITIES"
            else:
                out["resolution_state"] = "PARTIAL_TARGET_EVENT_PRESENT_IDENTITY_INCOMPLETE"
                out["remaining_unknowns"].append("ONE_OR_MORE_TARGET_EVENTS_LACK_RECORDDATE_OR_LIBERPAGE")
        else:
            out["resolution_state"] = "PARTIAL_TARGET_EVENT_SET"
            out["remaining_unknowns"].append("NOT_ALL_TARGET_EVENT_TYPES_PRESENT_IN_DATE_WINDOW")
        out["remaining_unknowns"].append("RECORDED_PARTY_ROLES_NOT_EXPOSED_BY_GIS")

    elif target == "HISTORICAL_RECORD_DATE_VALIDATION":
        # V17B intentionally kept this unresolved. V17C may classify field semantics
        # only when the returned county row itself exposes a recording identity.
        anomalous = [r for r in rows if r.get("document_date") == "1112-11-11"]
        identified = [r for r in anomalous if r.get("record_date") and r.get("liber_page")]
        if identified:
            r = identified[0]
            out["resolution_state"] = "RESOLVED_FIELD_LEVEL_DATE_ANOMALY"
            out["resolved_facts"] = [
                "ANOMALOUS_1112_VALUE_IS_DOCUMENT_DATE_FIELD_NOT_RECORDING_DATE",
                f"AUTHORITATIVE_RECORD_DATE_{r.get('record_date')}",
                f"AUTHORITATIVE_LIBER_PAGE_{r.get('liber_page')}"
            ]
            out["remaining_unknowns"].append("WHY_SOURCE_DOCUMENT_DATE_FIELD_CONTAINS_1112_11_11")
        else:
            out["remaining_unknowns"].append("AUTHORITATIVE_RECORD_IDENTITY_NOT_AVAILABLE")

    return out

def build_evidence_resolution_date_semantics_v17c():
    source = build_suffolk_county_transfer_history_retrieval_v17b()
    if source.get("status") not in ("ok","partial"):
        return {"status":"failed","version":VERSION,"error":"V17B prerequisite failed"}

    # V17B's historical-anomaly job already contains the full parcel result.
    # For the 2026 BSD edge case, inspect source-level records represented across
    # V17B results for the parcel without changing their date semantics.
    results = source.get("research_results") or []
    by_parcel = {}
    for r in results:
        by_parcel.setdefault(r.get("parcel_id"), [])
        for row in r.get("county_records_in_window") or []:
            key = (row.get("history_sequence"), row.get("liber_page"), row.get("record_date"),
                   row.get("document_code"), row.get("entry_date"))
            if key not in {(
                x.get("history_sequence"), x.get("liber_page"), x.get("record_date"),
                x.get("document_code"), x.get("entry_date")) for x in by_parcel[r.get("parcel_id")]}:
                by_parcel[r.get("parcel_id")].append(row)

    normalized = []
    for r in results:
        rr = dict(r)
        # RECORDED_INSTRUMENT_DETAIL may need an incomplete target row whose
        # RECORDDATE is null but whose ENTRYDATE places it in current county data.
        if r.get("evidence_target") == "RECORDED_INSTRUMENT_DETAIL":
            rows = list(r.get("county_records_in_window") or [])
            known = {x.get("history_sequence") for x in rows}
            for x in by_parcel.get(r.get("parcel_id"), []):
                if x.get("history_sequence") in known:
                    continue
                if x.get("document_code") == "BSD" and x.get("record_date") is None:
                    rows.append(x)
            rr["county_records_in_window"] = rows
        normalized.append(_resolve(rr))

    counts = {}
    for r in normalized:
        counts[r["resolution_state"]] = counts.get(r["resolution_state"],0) + 1

    return {
        "status":"ok",
        "version":VERSION,
        "mode":MODE,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "market_code":source.get("market_code"),
        "source_contract":{"version":source.get("version"),
                           "research_questions_received":len(results),
                           "query_errors":len(source.get("query_errors") or {})},
        "date_semantics_contract":{
            "RECORDDATE":"recording date; authoritative for recorded chronology",
            "DOCDATE":"instrument/document stated date; never substituted for RECORDDATE",
            "ENTRYDATE":"county system entry date; proves system presence only, never substituted for RECORDDATE",
            "silent_date_repair_allowed":False
        },
        "summary":{
            "research_questions_resolved_or_classified":len(normalized),
            "resolution_states":counts,
            "database_writes":0
        },
        "resolved_research":normalized,
        "guards":{
            "database_writes":False,
            "investigate_state_touched":False,
            "new_candidate_created":False,
            "recorddate_fabricated_from_entrydate":False,
            "recorddate_fabricated_from_documentdate":False,
            "source_history_silently_corrected":False,
            "grantor_grantee_claimed_from_gis":False,
            "manual_ownership_verification_bypassed":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False
        }
    }
