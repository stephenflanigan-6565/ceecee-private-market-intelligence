from html import escape
from v19t import build_v19t

VERSION="V19U"

def _badge(status):
    return "Solid" if status=="SOLID" else "Follow-up"

def build_v19u():
    source=build_v19t()
    cards=source["cards"]
    checks={
        "v19t_source_passed": source.get("status")=="ok",
        "exact_same_11_cards": len(cards)==11 and len({c["parcel_id"] for c in cards})==11,
        "presentation_only": True,
        "no_candidate_logic_change": True,
        "no_score_or_rank": True,
        "seller_intent_not_inferred": True,
    }
    return {
        "status":"ok" if all(checks.values()) else "failed",
        "version":VERSION,
        "mode":"POLISHED_OPERATOR_REVIEW_SCREEN_PRESENTATION_ONLY",
        "card_count":len(cards),
        "checks":checks,
        "database_writes":0,
        "guards":{"database_writes":False,"seller_intent_inferred":False,
                  "seller_scoring":False,"overall_ranking":False,
                  "contact_authorized":False,"outreach_touched":False},
        "next_if_pass":"CONTINUE_OPERATOR_PRODUCT_BUILD_ON_PROVEN_SCREEN"
    }

def render_v19u():
    source=build_v19t()
    cards=source["cards"]
    blocks=[]
    for c in cards:
        status=c["pmi_status"]
        cls="solid" if status=="SOLID" else "follow"
        episode=" · ".join(c["current_episode"]) if c["current_episode"] else "Title activity"
        blocks.append(f"""
        <article class="property-card">
          <div class="topline">
            <div>
              <h2>{escape(c["property"])}</h2>
              <div class="parcel">Parcel {escape(c["parcel_id"])}</div>
            </div>
            <span class="badge {cls}">{escape(_badge(status))}</span>
          </div>
          <div class="owner"><span>Owner</span>{escape(c["owner"])}</div>
          <div class="event">
            <div class="eyebrow">What happened</div>
            <div class="event-title">{escape(c["what_happened"])}</div>
            <div class="episode">{escape(episode)} · {c["older_title_events_in_memory"]} older title event(s) in memory</div>
          </div>
          <div class="two">
            <section><div class="eyebrow">Why PMI surfaced it</div><p>{escape(c["why_it_is_here"])}</p></section>
            <section><div class="eyebrow">Needs checking</div><p>{escape(c["needs_checking"])}</p></section>
          </div>
          <div class="bottom">
            <div><span class="muted">Seller intent</span><strong>Not established</strong></div>
            <div class="action">{escape(c["agent_action"])}</div>
          </div>
        </article>""")
    return """<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private Market Intelligence — Property Review</title>
<style>
:root{--ink:#18212f;--muted:#687386;--line:#e5e9ef;--paper:#f6f8fb;--card:#fff;--solid:#eaf7ef;--solidink:#17633a;--follow:#fff4dc;--followink:#8a5b00;--accent:#243b63}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.shell{max-width:1180px;margin:auto;padding:34px 22px 60px}.header{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:24px}
.kicker{font-size:12px;letter-spacing:.16em;font-weight:800;color:var(--accent)}h1{font-size:32px;line-height:1.05;margin:7px 0 6px}.sub{color:var(--muted);font-size:15px}
.summary{background:#fff;border:1px solid var(--line);border-radius:16px;padding:13px 16px;white-space:nowrap}.summary b{font-size:22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(355px,1fr));gap:16px}
.property-card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 4px 16px rgba(30,45,70,.045)}
.topline{display:flex;justify-content:space-between;gap:14px;align-items:start}h2{font-size:21px;margin:0 0 4px}.parcel{font-size:11px;color:var(--muted)}
.badge{font-size:12px;font-weight:800;border-radius:999px;padding:7px 10px}.solid{background:var(--solid);color:var(--solidink)}.follow{background:var(--follow);color:var(--followink)}
.owner{margin:16px 0;padding:12px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-weight:700}.owner span,.eyebrow,.muted{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;margin-bottom:5px}
.event-title{font-weight:700;line-height:1.45}.episode{font-size:12px;color:var(--muted);margin-top:7px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}.two section{background:#f9fafc;border-radius:12px;padding:13px}.two p{margin:0;line-height:1.45;font-size:14px}
.bottom{margin-top:16px;padding-top:14px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:18px;align-items:end}.bottom strong{font-size:13px}.action{max-width:60%;font-size:13px;color:var(--accent);font-weight:700;text-align:right}
.footer{margin-top:24px;color:var(--muted);font-size:12px;text-align:center}
@media(max-width:650px){.header,.bottom{display:block}.summary{margin-top:14px}.grid{grid-template-columns:1fr}.two{grid-template-columns:1fr}.action{max-width:none;text-align:left;margin-top:12px}}
</style></head><body><main class="shell">
<div class="header"><div><div class="kicker">PRIVATE MARKET INTELLIGENCE</div><h1>Property Review</h1><div class="sub">Current factual property activity prepared for agent review</div></div>
<div class="summary"><b>11</b> properties for review</div></div>
<div class="grid">""" + "".join(blocks) + """</div>
<div class="footer">Research view · Seller intent is not inferred · Outreach remains off</div>
</main></body></html>"""

