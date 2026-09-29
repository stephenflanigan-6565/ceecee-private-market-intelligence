#!/usr/bin/env python3
"""V16I — scheduled production run entrypoint.

Thin production entrypoint for DigitalOcean App Platform scheduled jobs.
It calls the locked V16H attention-delivery contract directly (no HTTP loopback),
prints one machine-readable JSON result to job logs, and exits non-zero when the
underlying pipeline reports a failure so App Platform can mark the invocation
failed. It does not send email/SMS and does not change seller logic.
"""
import json
import sys
from datetime import datetime, timezone

from attention_delivery_v16h import build_attention_delivery_v16h

VERSION = "V16I"
MODE = "SCHEDULED_PRODUCTION_RUN"


def run_scheduled_production_v16i():
    started = datetime.now(timezone.utc).isoformat()
    try:
        payload = build_attention_delivery_v16h()
        delivery = payload.get("delivery") or {}
        pipeline = payload.get("pipeline") or {}
        pipeline_failed = delivery.get("type") == "PIPELINE_FAILURE" or pipeline.get("status") == "degraded"

        result = {
            "status": "degraded" if pipeline_failed else "ok",
            "version": VERSION,
            "mode": MODE,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "schedule_contract": {
                "cadence": "DAILY",
                "local_time": "08:00",
                "time_zone": "America/New_York",
                "cron": "0 8 * * *",
            },
            "delivery_decision": {
                "send": bool(delivery.get("send")),
                "audience": delivery.get("audience"),
                "type": delivery.get("type"),
                "external_message_sent": False,
            },
            "attention_payload": payload,
            "guards": {
                "v16h_locked_contract_reused": True,
                "external_message_sent": False,
                "contact_authorized": False,
                "outreach_touched": False,
                "seller_intent_inferred": False,
                "seller_scoring": False,
            },
            "next_locked_step": "VERIFY_ONE_DIGITALOCEAN_SCHEDULED_JOB_INVOCATION_THEN_CONNECT_NOTIFICATION_TRANSPORT",
        }
        return result, (1 if pipeline_failed else 0)
    except Exception as exc:
        return {
            "status": "error",
            "version": VERSION,
            "mode": MODE,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "guards": {
                "external_message_sent": False,
                "contact_authorized": False,
                "outreach_touched": False,
            },
        }, 1


if __name__ == "__main__":
    result, exit_code = run_scheduled_production_v16i()
    print(json.dumps(result, sort_keys=True, default=str), flush=True)
    sys.exit(exit_code)
