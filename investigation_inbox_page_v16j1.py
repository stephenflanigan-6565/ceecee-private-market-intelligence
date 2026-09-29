#!/usr/bin/env python3
"""V16J1 — isolated Investigation Inbox HTML route repair.

Presentation only. Converts the already-proven V16J read-only inbox payload into
plain escaped HTML without Jinja/template evaluation. No database writes, no
state changes, no outreach, no contact authorization.
"""
from html import escape


def _e(value):
    return escape("" if value is None else str(value), quote=True)


def build_investigation_inbox_html_v16j1(data):
    count = int(data.get("investigate_count") or 0)
    items = data.get("items") or []
    parts = ["""<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Investigation Inbox</title><style>
body{font-family:Arial,sans-serif;max-width:980px;margin:36px auto;padding:0 18px;color:#171717}h1{margin-bottom:4px}.sub{color:#666;margin-bottom:24px}.empty,.item{border:1px solid #ddd;border-radius:12px;padding:18px;margin:12px 0}.tag{font-weight:700}.meta{color:#666;font-size:13px;margin-top:8px}.trigger{margin-top:12px;padding:10px;background:#f5f5f5;border-radius:8px}
</style></head><body><h1>Investigation Inbox</h1><div class=\"sub\">Westhampton Beach · durable INVESTIGATE state · read only</div>"""]
    if count == 0:
        parts.append('<div class="empty"><b>No properties require investigation.</b><br><span class="meta">The machine is quiet because no post-baseline operational change is currently in INVESTIGATE.</span></div>')
    for item in items:
        why = item.get("why_investigate") if isinstance(item, dict) else {}
        if not isinstance(why, dict):
            why = {}
        triggers = why.get("operational_triggers") or []
        parts.append('<div class="item">')
        parts.append(f'<div class="tag">INVESTIGATE · Parcel {_e(item.get("parcel_id"))}</div>')
        parts.append(f'<div class="meta">First entered: {_e(item.get("first_entered_at"))} · Triggers: {_e(item.get("trigger_count"))} · Contact authorized: NO</div>')
        for t in triggers:
            if not isinstance(t, dict):
                continue
            parts.append('<div class="trigger">')
            parts.append(f'<b>{_e(t.get("change_type"))}</b> · {_e(t.get("evidence_family"))} / {_e(t.get("evidence_type"))}<br>')
            parts.append(f'<span class="meta">Source: {_e(t.get("source"))} · Detected: {_e(t.get("detected_at"))}</span></div>')
        parts.append('</div>')
    parts.append(f'<div class="meta">Generated {_e(data.get("generated_at"))} · This screen does not infer seller intent or authorize outreach.</div></body></html>')
    return "".join(parts)
