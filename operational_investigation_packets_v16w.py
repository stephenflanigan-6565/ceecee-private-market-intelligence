#!/usr/bin/env python3
"""V16W — read-only operational investigation packet assembler.

Joins the durable V16J INVESTIGATE inbox to the proven V16R1 factual deeper-
research output. It does not create candidates, change investigation state,
authorize contact, infer seller intent, or expose owner names/addresses.
"""
from datetime import datetime, timezone
from investigation_inbox_v16j import build_investigation_inbox_v16j
from factual_research_resolution_v16r import build_factual_research_resolution_v16r

VERSION = "V16W"
MODE = "READ_ONLY_OPERATIONAL_INVESTIGATION_PACKET_ASSEMBLY"
MARKET = "WESTHAMPTON_BEACH_NY"

def build_operational_investigation_packets_v16w():
    inbox = build_investigation_inbox_v16j()
    research = build_factual_research_resolution_v16r()

    if inbox.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V16J prerequisite failed",
                "guards":{"database_writes":False,"investigate_state_touched":False,
                          "contact_authorized":False,"outreach_touched":False}}
    if research.get("status") != "ok":
        return {"status":"failed","version":VERSION,"error":"V16R1/V16R factual research prerequisite failed",
                "guards":{"database_writes":False,"investigate_state_touched":False,
                          "contact_authorized":False,"outreach_touched":False}}

    inbox_items = list(inbox.get("items") or [])
    research_items = list((research.get("resolved_research") or {}).get("items") or [])
    by_pid = {str(x.get("parcel_id")): x for x in research_items if x.get("parcel_id")}

    packets = []
    missing_research = []
    for item in inbox_items:
        pid = str(item.get("parcel_id"))
        r = by_pid.get(pid)
        if r is None:
            missing_research.append(pid)

        why = item.get("why_investigate") or {}
        packet = {
            "parcel_id": pid,
            "operational_state": item.get("state"),
            "first_entered_at": item.get("first_entered_at"),
            "last_evaluated_at": item.get("last_evaluated_at"),
            "why_investigate": {
                "basis_reasons": why.get("basis_reasons") or [],
                "current_event_reasons": why.get("current_event_reasons") or [],
                "temporal_state": why.get("temporal_state"),
                "source_basis": why.get("source_basis"),
                "operational_authority": why.get("operational_authority"),
            },
            "factual_research": {
                "available": r is not None,
                "queue_reasons": (r or {}).get("queue_reasons") or [],
                "research_answers": (r or {}).get("research_answers") or [],
                "chronology_tail": (r or {}).get("chronology_tail") or [],
                "ownership_reconciliation": (r or {}).get("ownership_reconciliation"),
            },
            "verification": {
                "ownership_verification_gate": why.get("ownership_verification_gate") or (r or {}).get("ownership_verification_gate"),
                "manual_owner_verification_required": bool(why.get("manual_owner_verification_required", False)),
                "contact_authorized": False,
            },
            "authority_boundary": {
                "seller_intent": False,
                "investigate_only": True,
                "owner_addressed_outreach_authorized": False,
            },
        }
        packets.append(packet)

    return {
        "status":"ok",
        "version":VERSION,
        "mode":MODE,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "market_code":MARKET,
        "source_contract":{
            "investigation_inbox_version":inbox.get("version"),
            "investigate_count":inbox.get("investigate_count"),
            "factual_research_version":research.get("version"),
            "factual_research_items_available":len(research_items),
        },
        "packet_summary":{
            "packet_count":len(packets),
            "all_investigate_records_have_factual_research":len(missing_research)==0,
            "missing_factual_research_parcel_ids":missing_research,
        },
        "investigation_packets":packets,
        "interpretation":[
            "Each packet is assembled only for a durable V16J INVESTIGATE record.",
            "The packet reuses proven factual research already held by PMI; it does not create a new seller signal.",
            "INVESTIGATE remains internal research authority only. Ownership verification and Contact Governor remain separate."
        ],
        "guards":{
            "database_writes":False,
            "investigate_state_touched":False,
            "seller_intent_inferred":False,
            "seller_scoring":False,
            "contact_authorized":False,
            "outreach_touched":False,
            "owner_names_addresses_emitted":False,
            "sensitive_motivation_inferred":False,
            "price_or_luxury_gate_used":False,
        }
    }
