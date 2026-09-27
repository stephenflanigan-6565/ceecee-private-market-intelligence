import os
from flask import Flask, jsonify, render_template_string
from operator_report import build_snapshot
from cloud_memory_check import verify_persistence
from universe_collector import probe as probe_westhampton_universe, populate as populate_westhampton_universe
from universe_profile import profile as profile_westhampton_universe

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
