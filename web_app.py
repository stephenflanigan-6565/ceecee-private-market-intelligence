import os
from flask import Flask, jsonify, render_template_string
from operator_report import build_snapshot
from cloud_memory_check import verify_persistence
from universe_collector import probe as probe_westhampton_universe, populate as populate_westhampton_universe
from universe_profile import profile as profile_westhampton_universe
from universe_classification import preview as preview_westhampton_classification, persist as persist_westhampton_classification
from ownership_transfer_probe import probe_owner_only, probe_transfer_only, probe_owner_handshake, probe_transfer_history_handshake, probe_internal_failure_isolation, probe_coverage_v15i, ingest_evidence_v15j
from assessment_probe import probe_assessment_v15k, persist_assessment_v15l
from derived_intelligence import profile_v15m, candidate_matrix_v15n, location_context_profile_v15p

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



@app.get("/api/westhampton-universe/assessment-probe-v15k")
def westhampton_assessment_probe_v15k():
    # V15K is deliberately read-only: prove official roll extraction + canonical join first.
    try:
        return jsonify(probe_assessment_v15k()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V15K2","mode":"READ_ONLY_NYS_ORPTS_ASSESSMENT_VALUE_SOURCE_PROBE",
                        "error_type":type(e).__name__,"error":str(e)[:240],"database_writes":0,
                        "assessment_data_touched":False,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/derived-intelligence-profile-v15m")
def westhampton_derived_intelligence_profile_v15m():
    try:
        return jsonify(profile_v15m()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15M","mode":"READ_ONLY_DERIVED_INTELLIGENCE_POPULATION_PROFILE",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/location-context-profile-v15p")
def westhampton_location_context_profile_v15p():
    try:
        return jsonify(location_context_profile_v15p()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15P","mode":"READ_ONLY_LOCATION_CONTEXT_PROFILE",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/candidate-intelligence-matrix-v15n")
def westhampton_candidate_intelligence_matrix_v15n():
    try:
        return jsonify(candidate_matrix_v15n()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15N","mode":"READ_ONLY_CANDIDATE_INTELLIGENCE_MATRIX",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/assessment-persist-v15l")
def westhampton_assessment_persist_v15l():
    try:
        return jsonify(persist_assessment_v15l()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V15L","mode":"ASSESSMENT_VALUE_EVIDENCE_PERSISTENCE",
                        "error_type":type(e).__name__,"error":str(e)[:240],
                        "seller_scoring_touched":False,"opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/evidence-persist-v15j")
def westhampton_evidence_persist_v15j():
    try:
        return jsonify(ingest_evidence_v15j()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V15J","mode":"OWNERSHIP_TRANSFER_EVIDENCE_PERSISTENCE",
                        "error_type":type(e).__name__,"error":str(e)[:240],
                        "seller_scoring_touched":False,"opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/coverage-v15i")
def westhampton_coverage_v15i():
    try:
        return jsonify(probe_coverage_v15i()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V15I","mode":"READ_ONLY_OWNERSHIP_TRANSFER_COVERAGE",
                        "error_type":type(e).__name__,"error":str(e)[:200],"database_writes":0,
                        "property_data_touched":False,"ownership_data_touched":False,"transfer_data_touched":False,
                        "seller_scoring_touched":False,"opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/internal-failure-isolation-v15h")
def westhampton_internal_failure_isolation_v15h():
    # Deliberately HTTP 200 even when a diagnostic stage fails so the platform cannot mask our evidence.
    try:
        return jsonify(probe_internal_failure_isolation()), 200
    except Exception as e:
        return jsonify({"status":"diagnostic_wrapper_failure","mode":"READ_ONLY_INTERNAL_FAILURE_ISOLATION",
                        "error_type":type(e).__name__,"error":str(e)[:160],
                        "database_writes":0,"property_data_touched":False,"ownership_data_touched":False,
                        "transfer_data_touched":False,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

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
