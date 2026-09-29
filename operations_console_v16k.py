#!/usr/bin/env python3
"""V16K — rough operations console. Read-only presentation over locked durable state."""
from datetime import datetime, timezone
from db import connect, execute
from investigation_inbox_v16j import build_investigation_inbox_v16j

VERSION='V16K'
MODE='READ_ONLY_OPERATIONS_CONSOLE'

def build_operations_console_v16k():
    conn=connect()
    try:
        def scalar(sql):
            row=execute(conn, sql).fetchone()
            return int((row[0] if row else 0) or 0)
        evidence=scalar('SELECT COUNT(*) FROM evidence_ledger')
        changes=scalar('SELECT COUNT(*) FROM evidence_change_events')
        states=scalar("SELECT COUNT(*) FROM investigation_state WHERE market_code='WESTHAMPTON_BEACH_NY' AND state='INVESTIGATE'")
        inbox=build_investigation_inbox_v16j()
        return {
            'status':'ok','version':VERSION,'mode':MODE,
            'generated_at':datetime.now(timezone.utc).isoformat(),
            'market_code':'WESTHAMPTON_BEACH_NY',
            'counts':{'evidence_records':evidence,'change_events':changes,'investigate':states},
            'inbox':{'investigate_count':inbox.get('investigate_count',0),'items':inbox.get('items',[])},
            'guards':{'database_writes':False,'external_message_sent':False,'outreach_touched':False,
                      'contact_authorized_by_console':False,'seller_scoring':False},
        }
    finally:
        conn.close()

def render_operations_console_v16k(data):
    c=data.get('counts',{})
    items=(data.get('inbox') or {}).get('items') or []
    cards=''.join([
        f'<div class="card"><div class="n">{c.get("evidence_records",0):,}</div><div>Evidence records</div></div>',
        f'<div class="card"><div class="n">{c.get("change_events",0):,}</div><div>Detected changes</div></div>',
        f'<div class="card"><div class="n">{c.get("investigate",0):,}</div><div>Investigate now</div></div>',
    ])
    if items:
        rows=''.join(f'<li><b>{str(x.get("parcel_id") or "Unknown parcel")}</b> — {str(x.get("why_investigate") or "Operational change requires review")}</li>' for x in items)
        queue=f'<h2>Investigation Queue</h2><ul>{rows}</ul>'
    else:
        queue='<div class="quiet"><b>Machine quiet.</b><br>No property is currently in INVESTIGATE.</div>'
    return f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Private Market Intelligence</title>
<style>body{{font-family:Arial,sans-serif;max-width:960px;margin:36px auto;padding:0 18px;color:#171717}}h1{{margin-bottom:4px}}.sub,.meta{{color:#666}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:12px;margin:26px 0}}.card,.quiet{{border:1px solid #ddd;border-radius:12px;padding:18px}}.n{{font-size:30px;font-weight:700}}a{{color:#111}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style></head><body>
<h1>Private Market Intelligence</h1><div class="sub">Westhampton Beach · rough operations console · read only</div>
<div class="grid">{cards}</div>{queue}
<p><a href="/investigations">Open Investigation Inbox</a></p>
<p class="meta">Generated {data.get('generated_at','')} · No outreach or seller scoring is authorized by this screen.</p>
</body></html>'''
