import os
from flask import Flask, jsonify, render_template_string
from operator_report import build_snapshot
from cloud_memory_check import verify_persistence
from universe_collector import probe as probe_westhampton_universe, populate as populate_westhampton_universe
from universe_profile import profile as profile_westhampton_universe
from universe_classification import preview as preview_westhampton_classification, persist as persist_westhampton_classification
from ownership_transfer_probe import probe_owner_only, probe_transfer_only, probe_owner_handshake, probe_transfer_history_handshake

app = Flask(__name__)

PAGE = """
<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CEECEE Private Market Intelligence</title>
<style>
body{font-family:Arial,sans-serif;max-width:920px;margin:40px auto;padding:0 18px;color:#171717}
h1{font-size:28px;margin-bottom:4px}.sub{color:#666;margin-bottom:28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}
.card{border:1px solid #ddd;border-radius:12px;padding:18px}.n{font-size:28px;font-weight:700}
.safe{margin-top:24px;padding:14px;border:1px solid #ddd;border-radius:10px}
small{color:#666}
</style></head>
<body>
<h1>CEECEE PRIVATE MARKET INTELLIGENCE</h1>
<div class="sub">Westhampton Beach Seller Opportunity Engine</div>
<div class="grid">
{% for key,val in data.opportunities.items() %}
<div class="card"><div class="n">{{ val }}</div><div>{{ key }}</div></div>
{% endfor %}
<div class="card"><div class="n">{{ data.contact_eligible }}</div><div>CONTACT ELIGIBLE</div></div>
<div class="card"><div class="n">{{ data.failures_24h }}</div><div>FAILURES 24H</div></div>
</div>
<div class="safe"><b>Research mode:</b> homeowner outreach remains OFF.<br>
<small>Database: {{ data.database_backend }} · Generated {{ data.generated_at }}</small></div>
</body></html>
"""

@app.get("/health")
def health():
    return jsonify({"status":"ok","service":"ceecee-private-market-intelligence"}), 200

@app.get("/api/cloud-memory-check")
def cloud_memory_check():
    try:
        return jsonify(verify_persistence()), 200
    except Exception as e:
        return jsonify({"status":"degraded","error":type(e).__name__}), 503

@app.get("/api/westhampton-universe/probe")
def westhampton_universe_probe():
    try:
        result = probe_westhampton_universe()
        code = 200 if result.get("status") == "ok" else 422
        return jsonify(result), code
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_PROBE","error":type(e).__name__,
                        "database_writes":0,"property_data_touched":False,"outreach_touched":False}), 503

@app.get("/api/westhampton-universe/populate-v15b")
def westhampton_universe_populate_v15b():
    try:
        result = populate_westhampton_universe()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"CANONICAL_UNIVERSE_POPULATION",
                        "error":type(e).__name__,"opportunity_data_touched":False,
                        "outreach_touched":False}), 503

@app.get("/api/westhampton-universe/profile-v15c")
def westhampton_universe_profile_v15c():
    try:
        return jsonify(profile_westhampton_universe()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_UNIVERSE_PROFILE",
                        "error":type(e).__name__,"database_writes":0,
                        "property_data_touched":False,"opportunity_data_touched":False,
                        "outreach_touched":False}), 503

@app.get("/api/westhampton-universe/classification-preview-v15d")
def westhampton_classification_preview_v15d():
    try:
        return jsonify(preview_westhampton_classification()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_CLASSIFICATION_PREVIEW",
                        "error":type(e).__name__,"database_writes":0,
                        "property_data_touched":False,"opportunity_data_touched":False,
                        "outreach_touched":False}), 503

@app.get("/api/westhampton-universe/classification-persist-v15e")
def westhampton_classification_persist_v15e():
    try:
        return jsonify(persist_westhampton_classification()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"FACTUAL_COHORT_PERSISTENCE",
                        "error":type(e).__name__,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 503

@app.get("/api/westhampton-universe/transfer-history-handshake-v15g")
def westhampton_transfer_history_handshake_v15g():
    try:
        return jsonify(probe_transfer_history_handshake()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_TRANSFER_HISTORY_HANDSHAKE",
                        "error":str(e)[:120],"database_writes":0,"ownership_data_touched":False,
                        "transfer_data_touched":False,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 503

@app.get("/api/westhampton-universe/owner-handshake-v15f2")
def westhampton_owner_handshake_v15f2():
    try:
        return jsonify(probe_owner_handshake()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_OWNER_SOURCE_HANDSHAKE",
                        "error":str(e)[:120],"database_writes":0,"ownership_data_touched":False,
                        "transfer_data_touched":False,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 503

@app.get("/api/westhampton-universe/owner-probe-v15f1")
def westhampton_owner_probe_v15f1():
    try:
        return jsonify(probe_owner_only()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_OWNER_SOURCE_DIAGNOSTIC",
                        "error":str(e)[:80],"database_writes":0,"ownership_data_touched":False,
                        "transfer_data_touched":False,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 503

@app.get("/api/westhampton-universe/transfer-probe-v15f1")
def westhampton_transfer_probe_v15f1():
    try:
        return jsonify(probe_transfer_only()), 200
    except Exception as e:
        return jsonify({"status":"degraded","mode":"READ_ONLY_CURRENT_TRANSFER_SOURCE_DIAGNOSTIC",
                        "error":str(e)[:80],"database_writes":0,"ownership_data_touched":False,
                        "transfer_data_touched":False,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 503

@app.get("/api/status")
def api_status():
    try:
        return jsonify(build_snapshot(False)), 200
    except Exception as e:
        return jsonify({"status":"degraded","error":type(e).__name__}), 503

@app.get("/")
def home():
    try:
        data=build_snapshot(False)
    except Exception:
        data={"generated_at":"database not connected yet","database_backend":"pending",
              "opportunities":{"IGNORE":0,"WATCH":0,"INVESTIGATE":0,"LATENT":0,"ACTIVE":0},
              "contact_eligible":0,"failures_24h":0}
    return render_template_string(PAGE,data=data)
