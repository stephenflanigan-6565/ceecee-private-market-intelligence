#!/usr/bin/env python3
"""V16J — read-only Investigation Inbox.

Human-facing view of the durable V16D investigation_state table. This module
creates no opportunities, changes no state, authorizes no contact, and sends no
messages. It only renders what the locked intelligence chain has already stored.
"""
import json
from datetime import datetime, timezone
from db import connect, execute

VERSION = "V16J"
MODE = "READ_ONLY_INVESTIGATION_INBOX"
PILOT = "WESTHAMPTON_BEACH_NY"


def _now():
    return datetime.now(timezone.utc).isoformat()


def build_investigation_inbox_v16j():
    c = connect()
    try:
        rows = execute(c, """SELECT parcel_id,state,reason_json,trigger_count,
          first_entered_at,last_evaluated_at,contact_authorized,seller_intent_inferred
          FROM investigation_state WHERE market_code=? AND state='INVESTIGATE'
          ORDER BY first_entered_at DESC, parcel_id""", (PILOT,)).fetchall()
        items = []
        for r in rows:
            try:
                why = json.loads(r[2]) if r[2] else {}
            except Exception:
                why = {"raw_reason": str(r[2] or "")}
            items.append({
                "parcel_id": str(r[0]), "state": str(r[1]), "why_investigate": why,
                "trigger_count": int(r[3] or 0), "first_entered_at": r[4],
                "last_evaluated_at": r[5], "contact_authorized": bool(r[6]),
                "seller_intent_inferred": bool(r[7])
            })
        return {
            "status":"ok", "version":VERSION, "mode":MODE, "generated_at":_now(),
            "market_code":PILOT, "investigate_count":len(items), "items":items,
            "guards":{"database_writes":False,"contact_authorized_by_inbox":False,
                      "external_message_sent":False,"outreach_touched":False,
                      "seller_intent_inferred_by_inbox":False,"seller_scoring":False},
            "interpretation":"This inbox displays durable V16D INVESTIGATE state only; it does not create or rank seller opportunities."
        }
    finally:
        c.close()
