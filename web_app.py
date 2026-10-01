import os
from flask import Flask, jsonify, render_template_string
from operator_report import build_snapshot
from cloud_memory_check import verify_persistence
from universe_collector import probe as probe_westhampton_universe, populate as populate_westhampton_universe
from universe_profile import profile as profile_westhampton_universe
from universe_classification import preview as preview_westhampton_classification, persist as persist_westhampton_classification
from ownership_transfer_probe import probe_owner_only, probe_transfer_only, probe_owner_handshake, probe_transfer_history_handshake, probe_internal_failure_isolation, probe_coverage_v15i, ingest_evidence_v15j
from assessment_probe import probe_assessment_v15k, persist_assessment_v15l
from derived_intelligence import profile_v15m, candidate_matrix_v15n, location_context_profile_v15p, candidate_research_cohorts_v15q, transfer_date_quality_guard_v15r, transfer_intelligence_foundation_v15s, seller_opportunity_research_framework_v15t, market_exposure_evidence_readiness_v15u, property_parcel_change_event_evidence_v15v, permit_building_change_source_readiness_v15w
from evidence_memory import build_evidence_memory_v16a
from change_detection import build_change_detection_v16b
from opportunity_pathways import build_opportunity_pathways_v16c
from investigation_queue import build_investigation_queue_v16d
from positive_detection_validation_v16f import run_positive_detection_validation_v16f
from automated_pipeline_v16g import run_guarded_pipeline_v16g
from attention_delivery_v16h import build_attention_delivery_v16h
from live_evidence_refresh_v16e4c import refresh_suffolk_live_evidence_v16e4b
from investigation_inbox_v16j import build_investigation_inbox_v16j
from investigation_inbox_page_v16j1 import build_investigation_inbox_html_v16j1
from operations_console_v16k import build_operations_console_v16k, render_operations_console_v16k
from title_transfer_event_intelligence_v16l import build_title_transfer_event_intelligence_v16l
from title_transfer_authority_v16m import build_title_transfer_authority_v16m
from title_transfer_sequence_v16n import build_title_transfer_sequence_v16n
from current_event_attention_v16o import build_current_event_attention_v16o
from multi_evidence_candidate_context_v16p import build_multi_evidence_candidate_context_v16p
from deeper_research_queue_v16q import build_deeper_research_queue_v16q
from factual_research_resolution_v16r import build_factual_research_resolution_v16r
from temporal_relevance_cleanup_v16s import build_temporal_relevance_cleanup_v16s
from explainable_investigation_basis_v16t import build_explainable_investigation_basis_v16t
from investigate_promotion_governance_v16u import build_investigate_promotion_governance_v16u
from investigate_state_transition_v16v import build_investigate_state_transition_v16v

app = Flask(__name__)

PAGE = """
<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private Market Intelligence</title>
<style>
body{font-family:Arial,sans-serif;max-width:920px;margin:40px auto;padding:0 18px;color:#171717}
h1{font-size:28px;margin-bottom:4px}.sub{color:#666;margin-bottom:28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}
.card{border:1px solid #ddd;border-radius:12px;padding:18px}.n{font-size:28px;font-weight:700}
.safe{margin-top:24px;padding:14px;border:1px solid #ddd;border-radius:10px}
small{color:#666}
</style></head>
<body>
<h1>PRIVATE MARKET INTELLIGENCE</h1>
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

@app.get("/api/westhampton-universe/candidate-research-cohorts-v15q")
def westhampton_candidate_research_cohorts_v15q():
    try:
        return jsonify(candidate_research_cohorts_v15q()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15Q","mode":"READ_ONLY_CANDIDATE_RESEARCH_COHORT_PREVIEW",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/transfer-date-quality-guard-v15r")
def westhampton_transfer_date_quality_guard_v15r():
    try:
        return jsonify(transfer_date_quality_guard_v15r()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15R","mode":"READ_ONLY_TRANSFER_DATE_DATA_QUALITY_GUARD",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/guarded-transfer-intelligence-v15s")
def westhampton_guarded_transfer_intelligence_v15s():
    try:
        return jsonify(transfer_intelligence_foundation_v15s()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15S","mode":"READ_ONLY_GUARDED_TRANSFER_INTELLIGENCE_FOUNDATION",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/intelligence/evidence-memory-v16a")
def evidence_memory_v16a():
    try:
        return jsonify(build_evidence_memory_v16a()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16A","mode":"PERSISTENT_EVIDENCE_MEMORY_FOUNDATION",
                        "error_type":type(e).__name__,"error":str(e)[:300],"watch_state_touched":False,
                        "investigate_state_touched":False,"opportunity_state_touched":False,"outreach_touched":False}), 200

@app.get("/api/intelligence/change-detection-v16b")
def change_detection_v16b():
    try:
        return jsonify(build_change_detection_v16b()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16B","mode":"CHANGE_DETECTION_AGAINST_EVIDENCE_MEMORY",
                        "error_type":type(e).__name__,"error":str(e)[:300],"watch_state_touched":False,
                        "investigate_state_touched":False,"opportunity_state_touched":False,"outreach_touched":False}), 200

@app.get("/api/intelligence/opportunity-pathways-v16c")
def opportunity_pathways_v16c():
    try:
        return jsonify(build_opportunity_pathways_v16c()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16C","mode":"FACTUAL_EVIDENCE_INTERPRETATION_AND_OPPORTUNITY_PATHWAYS",
                        "error_type":type(e).__name__,"error":str(e)[:300],"seller_scoring":False,
                        "watch_state_touched":False,"investigate_state_touched":False,"opportunity_state_touched":False,
                        "outreach_touched":False,"contact_authorized":False}), 200


@app.get("/api/intelligence/live-evidence-refresh-v16e4c")
def live_evidence_refresh_v16e4b():
    try:return jsonify(refresh_suffolk_live_evidence_v16e4b()), 200
    except Exception as e:return jsonify({"status":"degraded","version":"V16E4c","mode":"SUFFOLK_LIVE_EVIDENCE_REFRESH_TRANSFER_UNIQUE_KEY_REPAIR","error_type":type(e).__name__,"error":str(e)[:600],"contact_authorized":False,"outreach_touched":False,"seller_intent_inferred":False,"seller_scoring":False}), 200

@app.get("/api/intelligence/attention-delivery-v16h")
def attention_delivery_v16h():
    try:
        return jsonify(build_attention_delivery_v16h()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16H","mode":"ATTENTION_ONLY_DELIVERY_PAYLOAD",
                        "error_type":type(e).__name__,"error":str(e)[:600],"external_message_sent":False,
                        "contact_authorized":False,"outreach_touched":False,
                        "seller_intent_inferred":False,"seller_scoring":False}), 200

@app.get("/api/intelligence/automated-pipeline-v16g")
def automated_pipeline_v16g():
    try:
        return jsonify(run_guarded_pipeline_v16g()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16G","mode":"GUARDED_AUTOMATED_INTELLIGENCE_PIPELINE_RUNNER",
                        "error_type":type(e).__name__,"error":str(e)[:600],"contact_authorized":False,
                        "outreach_touched":False,"seller_intent_inferred":False,"seller_scoring":False}), 200

@app.get("/api/intelligence/positive-detection-validation-v16f")
def positive_detection_validation_v16f():
    try:
        return jsonify(run_positive_detection_validation_v16f()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16F","mode":"CONTROLLED_POSITIVE_DETECTION_VALIDATION",
                        "error_type":type(e).__name__,"error":str(e)[:600],
                        "database_writes":False,"contact_authorized":False,
                        "outreach_touched":False,"seller_intent_inferred":False,"seller_scoring":False}), 200


INBOX_PAGE = """
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Investigation Inbox</title><style>
body{font-family:Arial,sans-serif;max-width:980px;margin:36px auto;padding:0 18px;color:#171717}h1{margin-bottom:4px}.sub{color:#666;margin-bottom:24px}.empty,.item{border:1px solid #ddd;border-radius:12px;padding:18px;margin:12px 0}.tag{font-weight:700}.meta{color:#666;font-size:13px;margin-top:8px}.trigger{margin-top:12px;padding:10px;background:#f5f5f5;border-radius:8px}a{color:inherit}
</style></head><body><h1>Investigation Inbox</h1><div class="sub">Westhampton Beach · durable INVESTIGATE state · read only</div>
{% if data.investigate_count == 0 %}<div class="empty"><b>No properties require investigation.</b><br><span class="meta">The machine is quiet because no post-baseline operational change is currently in INVESTIGATE.</span></div>{% endif %}
{% for item in data.items %}<div class="item"><div class="tag">INVESTIGATE · Parcel {{ item.parcel_id }}</div><div class="meta">First entered: {{ item.first_entered_at }} · Triggers: {{ item.trigger_count }} · Contact authorized: NO</div>{% for t in item.why_investigate.operational_triggers %}<div class="trigger"><b>{{ t.change_type }}</b> · {{ t.evidence_family }} / {{ t.evidence_type }}<br><span class="meta">Source: {{ t.source }} · Detected: {{ t.detected_at }}</span></div>{% endfor %}</div>{% endfor %}
<div class="meta">Generated {{ data.generated_at }} · This screen does not infer seller intent or authorize outreach.</div></body></html>
"""


@app.get("/api/intelligence/title-transfer-event-intelligence-v16l")
def title_transfer_event_intelligence_v16l_api():
    try:
        return jsonify(build_title_transfer_event_intelligence_v16l()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V16L1","error":str(e)}), 500

@app.get("/api/intelligence/operations-console-v16k")
def operations_console_v16k_api():
    try:
        return jsonify(build_operations_console_v16k()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V16K","mode":"READ_ONLY_OPERATIONS_CONSOLE","error_type":type(e).__name__,"error":str(e)[:200],"guards":{"database_writes":False,"external_message_sent":False,"outreach_touched":False}}), 200

@app.get("/operations")
def operations_console_v16k_page():
    try:
        data=build_operations_console_v16k()
        return render_operations_console_v16k(data), 200, {"Content-Type":"text/html; charset=utf-8"}
    except Exception as e:
        return f"Operations console unavailable: {type(e).__name__}", 500, {"Content-Type":"text/plain; charset=utf-8"}

@app.get("/api/intelligence/investigation-inbox-v16j")
def investigation_inbox_v16j_api():
    try:
        return jsonify(build_investigation_inbox_v16j()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16J","mode":"READ_ONLY_INVESTIGATION_INBOX",
                        "error_type":type(e).__name__,"error":str(e)[:400],"database_writes":False,
                        "contact_authorized":False,"outreach_touched":False,"seller_intent_inferred":False}), 200

@app.get("/investigations")
def investigation_inbox_v16j_page():
    try:
        data=build_investigation_inbox_v16j()
        return build_investigation_inbox_html_v16j1(data), 200, {"Content-Type":"text/html; charset=utf-8"}
    except Exception as e:
        body=("<!doctype html><html><body><h1>Investigation Inbox</h1>"
              "<p>The inbox could not be rendered.</p><p>Read-only route; no data was changed.</p></body></html>")
        return body, 500, {"Content-Type":"text/html; charset=utf-8"}

@app.get("/api/intelligence/investigation-queue-v16d")
def investigation_queue_v16d():
    try:
        return jsonify(build_investigation_queue_v16d()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16D","mode":"OPERATIONAL_INVESTIGATION_STATE_AND_EXPLAINABLE_QUEUE",
                        "error_type":type(e).__name__,"error":str(e)[:300],"seller_scoring":False,
                        "seller_intent_inferred":False,"outreach_touched":False,"contact_authorized":False}), 200

@app.get("/api/westhampton-universe/permit-building-change-source-readiness-v15w")
def westhampton_permit_building_change_source_readiness_v15w():
    try:
        return jsonify(permit_building_change_source_readiness_v15w()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V15W","mode":"READ_ONLY_PERMIT_BUILDING_CHANGE_SOURCE_READINESS",
                        "error_type":type(e).__name__,"error":str(e)[:240],"database_writes":0,
                        "seller_scoring_touched":False,"watch_state_touched":False,"investigate_state_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/property-parcel-change-events-v15v")
def westhampton_property_parcel_change_events_v15v():
    try:
        return jsonify(property_parcel_change_event_evidence_v15v()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V15V","mode":"READ_ONLY_PROPERTY_PARCEL_CHANGE_EVENT_EVIDENCE",
                        "error_type":type(e).__name__,"error":str(e)[:240],"database_writes":0,
                        "seller_scoring_touched":False,"watch_state_touched":False,"investigate_state_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/market-exposure-evidence-readiness-v15u")
def westhampton_market_exposure_evidence_readiness_v15u():
    try:
        return jsonify(market_exposure_evidence_readiness_v15u()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15U","mode":"READ_ONLY_MARKET_EXPOSURE_EVIDENCE_READINESS",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "watch_state_touched":False,"investigate_state_touched":False,
                        "opportunity_data_touched":False,"outreach_touched":False}), 200

@app.get("/api/westhampton-universe/seller-opportunity-research-framework-v15t")
def westhampton_seller_opportunity_research_framework_v15t():
    try:
        return jsonify(seller_opportunity_research_framework_v15t()), 200
    except Exception as exc:
        return jsonify({"status":"degraded","version":"V15T","mode":"READ_ONLY_UNIVERSAL_SELLER_OPPORTUNITY_RESEARCH_FRAMEWORK",
                        "error":str(exc),"database_writes":0,"seller_scoring_touched":False,
                        "watch_state_touched":False,"investigate_state_touched":False,
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


@app.get("/api/intelligence/title-transfer-authority-v16m")
def title_transfer_authority_v16m_route():
    return jsonify(build_title_transfer_authority_v16m())

@app.get("/api/intelligence/title-transfer-sequence-v16n")
def title_transfer_sequence_v16n_route():
    return jsonify(build_title_transfer_sequence_v16n())

@app.get("/api/intelligence/current-event-attention-v16o")
def current_event_attention_v16o_route():
    return jsonify(build_current_event_attention_v16o())

@app.get("/api/intelligence/multi-evidence-candidate-context-v16p")
def multi_evidence_candidate_context_v16p_route():
    return jsonify(build_multi_evidence_candidate_context_v16p())


@app.get("/api/intelligence/deeper-research-queue-v16q")
def deeper_research_queue_v16q_route():
    return jsonify(build_deeper_research_queue_v16q())


@app.get("/api/intelligence/factual-research-resolution-v16r")
def factual_research_resolution_v16r_route():
    try:
        return jsonify(build_factual_research_resolution_v16r()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16R","mode":"READ_ONLY_FACTUAL_DEEPER_RESEARCH_RESOLUTION",
                        "error_type":type(e).__name__,"error":str(e)[:600],
                        "database_writes":False,"investigate_state_touched":False,
                        "contact_authorized":False,"outreach_touched":False,
                        "seller_intent_inferred":False,"seller_scoring":False}), 200


@app.get("/api/intelligence/temporal-relevance-cleanup-v16s")
def temporal_relevance_cleanup_v16s_route():
    try:
        return jsonify(build_temporal_relevance_cleanup_v16s()), 200
    except Exception as e:
        return jsonify({"status":"degraded","version":"V16S","mode":"READ_ONLY_TEMPORAL_RELEVANCE_CLEANUP",
                        "error_type":type(e).__name__,"error":str(e)[:600],
                        "database_writes":False,"investigate_state_touched":False,
                        "contact_authorized":False,"outreach_touched":False,
                        "seller_intent_inferred":False,"seller_scoring":False}), 200


@app.get("/api/intelligence/explainable-investigation-basis-v16t")
def explainable_investigation_basis_v16t_route():
    try:
        return jsonify(build_explainable_investigation_basis_v16t()), 200
    except Exception as exc:
        return jsonify({"status": "failed", "version": "V16T", "error": str(exc)}), 500


@app.get("/api/intelligence/investigate-promotion-governance-v16u")
def investigate_promotion_governance_v16u_route():
    try:
        return jsonify(build_investigate_promotion_governance_v16u()), 200
    except Exception as exc:
        return jsonify({"status": "failed", "version": "V16U", "error": str(exc)}), 500


@app.get("/api/intelligence/investigate-state-transition-v16v")
def investigate_state_transition_v16v_route():
    try:
        return jsonify(build_investigate_state_transition_v16v()), 200
    except Exception as exc:
        return jsonify({"status": "failed", "version": "V16V", "mode": "CONTROLLED_OPERATIONAL_INVESTIGATE_STATE_TRANSITION",
                        "error_type": type(exc).__name__, "error": str(exc)[:300],
                        "contact_authorized": False, "seller_intent_inferred": False,
                        "seller_scoring": False, "outreach_touched": False}), 200
