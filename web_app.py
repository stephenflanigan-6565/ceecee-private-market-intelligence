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
from operational_investigation_packets_v16w import build_operational_investigation_packets_v16w
from investigation_analyst_brief_v16x import build_investigation_analyst_brief_v16x
from research_question_triage_v16y import build_research_question_triage_v16y
from targeted_source_detail_enrichment_v16z import build_targeted_source_detail_enrichment_plan_v16z
from suffolk_clerk_retrieval_adapter_v17a import build_suffolk_clerk_retrieval_adapter_contract_v17a
from suffolk_county_transfer_history_v17b import build_suffolk_county_transfer_history_retrieval_v17b
from evidence_resolution_date_semantics_v17c import build_evidence_resolution_date_semantics_v17c
from authoritative_research_evidence_memory_v17d import build_authoritative_research_evidence_memory_v17d

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


@app.get("/api/intelligence/operational-investigation-packets-v16w")
def operational_investigation_packets_v16w_route():
    try:
        return jsonify(build_operational_investigation_packets_v16w()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V16W",
                        "mode":"READ_ONLY_OPERATIONAL_INVESTIGATION_PACKET_ASSEMBLY",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"database_writes":False,"investigate_state_touched":False,
                                  "contact_authorized":False,"outreach_touched":False}}), 200



@app.get("/api/intelligence/investigation-analyst-brief-v16x")
def investigation_analyst_brief_v16x_route():
    try:
        return jsonify(build_investigation_analyst_brief_v16x()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V16X",
                        "mode":"READ_ONLY_INVESTIGATION_ANALYST_BRIEF",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"database_writes":False,"investigate_state_touched":False,
                                  "contact_authorized":False,"outreach_touched":False}}), 200


@app.get("/api/intelligence/research-question-triage-v16y")
def research_question_triage_v16y_route():
    try:
        return jsonify(build_research_question_triage_v16y()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V16Y",
                        "mode":"READ_ONLY_RESEARCH_QUESTION_TRIAGE",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"database_writes":False,"investigate_state_touched":False,
                                  "contact_authorized":False,"outreach_touched":False}}), 200


@app.get("/api/intelligence/targeted-source-detail-enrichment-v16z")
def targeted_source_detail_enrichment_v16z_route():
    try:
        return jsonify(build_targeted_source_detail_enrichment_plan_v16z()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V16Z",
                        "mode":"READ_ONLY_TARGETED_SOURCE_DETAIL_ENRICHMENT_PLAN",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"database_writes":False,"contact_authorized":False,
                                  "seller_intent_inferred":False,"external_retrieval_performed":False}}), 200

@app.get("/api/intelligence/suffolk-clerk-retrieval-adapter-v17a")
def suffolk_clerk_retrieval_adapter_v17a_route():
    try:
        return jsonify(build_suffolk_clerk_retrieval_adapter_contract_v17a()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17A","error_type":type(e).__name__,"error":str(e)[:400]}), 200


@app.get("/api/intelligence/suffolk-county-transfer-history-v17b")
def suffolk_county_transfer_history_v17b_route():
    try:
        payload = build_suffolk_county_transfer_history_retrieval_v17b()
        return jsonify(payload), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17B",
                        "mode":"READ_ONLY_SUFFOLK_COUNTY_GIS_TRANSFER_HISTORY_RETRIEVAL",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"database_writes":False,"clerk_kiosk_scraped":False,
                                  "contact_authorized":False,"seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/evidence-resolution-date-semantics-v17c")
def evidence_resolution_date_semantics_v17c_route():
    try:
        return jsonify(build_evidence_resolution_date_semantics_v17c()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17C",
                        "mode":"READ_ONLY_EVIDENCE_RESOLUTION_AND_DATE_SEMANTICS",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"database_writes":False,
                                  "recorddate_fabricated_from_entrydate":False,
                                  "source_history_silently_corrected":False,
                                  "contact_authorized":False,
                                  "seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/authoritative-research-evidence-memory-v17d")
def authoritative_research_evidence_memory_v17d_route():
    try:
        return jsonify(build_authoritative_research_evidence_memory_v17d()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17D","mode":"PERSISTENT_AUTHORITATIVE_RESEARCH_EVIDENCE_MEMORY",
                        "error_type":type(e).__name__,"error":str(e)[:400],
                        "guards":{"v16a_evidence_ledger_modified":False,"investigate_state_touched":False,
                                  "contact_authorized":False,"seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/v17e2-route-probe")
def v17e2_route_probe():
    return jsonify({
        "status": "ok",
        "version": "V17E2",
        "mode": "ROUTE_REGISTRATION_PROBE_ONLY",
        "baseline": "V17D_PROVEN_LOCKED",
        "intelligence_logic_loaded": False,
        "database_access": False,
        "database_writes": False,
        "message": "Route registration is alive. No V17E re-evaluation logic executed."
    }), 200


@app.get("/api/intelligence/persistent-evidence-reevaluation-v17e3")
def persistent_evidence_reevaluation_v17e3_route():
    try:
        from persistent_evidence_reevaluation_v17e3 import build_persistent_evidence_reevaluation_v17e3
        return jsonify(build_persistent_evidence_reevaluation_v17e3()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17E3",
            "mode":"PERSISTENT_EVIDENCE_REEVALUATION_CONTAINED",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"investigate_state_touched":False,
                "contact_authorized":False,"seller_intent_inferred":False}}), 200

@app.get('/api/intelligence/unresolved-research-router-v17f')
def unresolved_research_router_v17f_route():
    try:
        from unresolved_research_router_v17f import build_unresolved_research_router_v17f
        return jsonify(build_unresolved_research_router_v17f()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'V17F','mode':'UNRESOLVED_FACTUAL_RESEARCH_ROUTER_READ_ONLY',
                        'error_type':type(e).__name__,'error':str(e)[:1200],
                        'guards':{'database_writes':False,'external_retrieval_performed':False,
                                  'investigate_state_touched':False,'contact_authorized':False,
                                  'seller_intent_inferred':False}}), 200


@app.get("/api/intelligence/manual-verification-packet-v17g")
def manual_verification_packet_v17g_route():
    try:
        from manual_verification_packet_v17g import build_manual_verification_packet_v17g
        return jsonify(build_manual_verification_packet_v17g()), 200
    except Exception as e:
        return jsonify({
            "status":"error","version":"V17G",
            "mode":"MANUAL_VERIFICATION_PACKET_EVIDENCE_RETURN_CONTRACT_READ_ONLY",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"external_retrieval_performed":False,
                      "investigate_state_touched":False,"contact_authorized":False,
                      "seller_intent_inferred":False}
        }), 200


@app.get("/api/intelligence/verified-evidence-intake-gate-v17h")
def verified_evidence_intake_gate_v17h_route():
    try:
        from verified_evidence_intake_gate_v17h import build_verified_evidence_intake_gate_v17h
        return jsonify(build_verified_evidence_intake_gate_v17h()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17H",
            "mode":"VERIFIED_EVIDENCE_INTAKE_VALIDATION_GATE",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"investigate_state_touched":False,
                      "contact_authorized":False,"seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/verified-evidence-persistence-v17i")
def verified_evidence_persistence_v17i_route():
    try:
        from verified_evidence_persistence_v17i import build_verified_evidence_persistence_v17i
        return jsonify(build_verified_evidence_persistence_v17i()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17I",
            "mode":"VERIFIED_EVIDENCE_APPEND_ONLY_PERSISTENCE_TEST",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"investigate_state_touched":False,"contact_authorized":False,
                      "seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/operational-verified-evidence-intake-v17j")
def operational_verified_evidence_intake_v17j_route():
    try:
        from operational_verified_evidence_intake_v17j import build_operational_verified_evidence_intake_v17j
        return jsonify(build_operational_verified_evidence_intake_v17j()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17J",
            "mode":"OPERATIONAL_VERIFIED_EVIDENCE_INTAKE_READINESS",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"investigate_state_touched":False,
                      "contact_authorized":False,"seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/verification-work-queue-v17k")
def verification_work_queue_v17k_route():
    try:
        from verification_work_queue_v17k import build_verification_work_queue_v17k
        return jsonify(build_verification_work_queue_v17k()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17K",
            "mode":"VERIFICATION_WORK_QUEUE_RETURN_CAPTURE_CONTRACT",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"investigate_state_touched":False,
                      "contact_authorized":False,"seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/full-universe-reevaluation-readiness-v17l")
def full_universe_reevaluation_readiness_v17l_route():
    try:
        from full_universe_reevaluation_readiness_v17l import build_full_universe_reevaluation_readiness_v17l
        return jsonify(build_full_universe_reevaluation_readiness_v17l()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17L",
            "mode":"FULL_UNIVERSE_REEVALUATION_READINESS_READ_ONLY",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"change_rescan_executed":False,
                      "investigate_state_touched":False,"contact_authorized":False,
                      "seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/full-universe-reevaluation-readiness-v17l1")
def full_universe_reevaluation_readiness_v17l1_route():
    try:
        from full_universe_reevaluation_readiness_v17l1 import build_full_universe_reevaluation_readiness_v17l1
        return jsonify(build_full_universe_reevaluation_readiness_v17l1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17L1",
            "mode":"FULL_UNIVERSE_REEVALUATION_READINESS_EVIDENCE_FAMILY_REPAIR",
            "error_type":type(e).__name__,"error":str(e)[:1200],
            "guards":{"database_writes":False,"change_rescan_executed":False,
                      "investigate_state_touched":False,"contact_authorized":False,
                      "seller_intent_inferred":False}}), 200


@app.get("/api/intelligence/self-contained-factual-rescan-v17m2")
def self_contained_factual_rescan_v17m2_route():
    try:
        from self_contained_factual_rescan_v17m2 import build_self_contained_factual_rescan_v17m2
        return jsonify(build_self_contained_factual_rescan_v17m2()), 200
    except Exception as e:
        return jsonify({
          "status":"error","version":"V17M2",
          "mode":"SELF_CONTAINED_PERSISTENT_EVIDENCE_FACTUAL_RESCAN_V16A_SCHEMA",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"external_retrievals":False,
                    "investigate_state_touched":False,"new_candidate_created":False,
                    "seller_intent_inferred":False,"contact_authorized":False}
        }),200


@app.get("/api/intelligence/controlled-transfer-source-refresh-v17n")
def controlled_transfer_source_refresh_v17n_route():
    try:
        from controlled_transfer_source_refresh_v17n import build_controlled_transfer_source_refresh_v17n
        return jsonify(build_controlled_transfer_source_refresh_v17n()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17N",
          "mode":"CONTROLLED_TRANSFER_SOURCE_REFRESH_DELTA_COMPARISON_READ_ONLY",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,
                    "new_candidate_created":False,"seller_intent_inferred":False,
                    "contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/controlled-transfer-source-refresh-v17n1")
def controlled_transfer_source_refresh_v17n1_route():
    try:
        from controlled_transfer_source_refresh_v17n1 import build_controlled_transfer_source_refresh_v17n1
        return jsonify(build_controlled_transfer_source_refresh_v17n1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17N1",
          "mode":"CONTROLLED_TRANSFER_SOURCE_REFRESH_CANONICAL_DELTA_REPAIR",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,
                    "new_candidate_created":False,"seller_intent_inferred":False,
                    "contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/genuine-refresh-delta-validation-v17o")
def genuine_refresh_delta_validation_v17o_route():
    try:
        from genuine_refresh_delta_validation_v17o import build_genuine_refresh_delta_validation_v17o
        return jsonify(build_genuine_refresh_delta_validation_v17o()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17O","mode":"GENUINE_REFRESH_DELTA_VALIDATION_READ_ONLY",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,
                    "new_candidate_created":False,"seller_intent_inferred":False,
                    "contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/eight-delta-event-semantics-v17p")
def eight_delta_event_semantics_v17p_route():
    try:
        from eight_delta_event_semantics_v17p import build_eight_delta_event_semantics_v17p
        return jsonify(build_eight_delta_event_semantics_v17p()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17P",
          "mode":"EIGHT_DELTA_EVENT_SEMANTICS_RESEARCH_QUESTION_GATE_READ_ONLY",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,
                    "new_candidate_created":False,"seller_intent_inferred":False,
                    "contact_authorized":False,"clerk_kiosk_scraped":False}}), 200

@app.get("/api/intelligence/delta-specific-research-packets-v17q1")
def delta_specific_research_packets_v17q1_route():
    try:
        from delta_specific_research_packets_v17q import build_delta_specific_research_packets_v17q
        return jsonify(build_delta_specific_research_packets_v17q()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17Q1","mode":"DELTA_SPECIFIC_FACTUAL_RESEARCH_QUESTION_REEVALUATION_PACKETS_READ_ONLY",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
          "seller_intent_inferred":False,"contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/research-question-source-routing-v17r")
def research_question_source_routing_v17r_route():
    try:
        from research_question_source_routing_v17r import build_research_question_source_routing_v17r
        return jsonify(build_research_question_source_routing_v17r()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17R","mode":"FACTUAL_RESEARCH_QUESTION_MEMORY_VS_FRESH_SOURCE_ROUTING_READ_ONLY",
          "error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
          "seller_intent_inferred":False,"contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/v17s")
def v17s_route():
    try:
        from v17s import build_v17s
        return jsonify(build_v17s()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17S","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
          "seller_intent_inferred":False,"contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/v17t")
def v17t_route():
    try:
        from v17t import build_v17t
        return jsonify(build_v17t()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17T","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
          "seller_intent_inferred":False,"contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/v17u")
def v17u_route():
    try:
        from v17u import build_v17u
        return jsonify(build_v17u()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17U","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
          "seller_intent_inferred":False,"contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/v17v")
def v17v_route():
    try:
        from v17v import build_v17v
        return jsonify(build_v17v()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17V","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
          "seller_intent_inferred":False,"contact_authorized":False,"clerk_kiosk_scraped":False}}), 200


@app.get("/api/intelligence/v17w")
def v17w_route():
    try:
        from v17w import build_v17w
        return jsonify(build_v17w()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17W","error_type":type(e).__name__,"error":str(e)[:1200]}), 200


@app.get("/api/intelligence/v17w1")
def v17w1_route():
    try:
        from v17w1 import build_v17w1
        return jsonify(build_v17w1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17W1","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False}}), 200


@app.get("/api/intelligence/v17w2")
def v17w2_route():
    try:
        from v17w2 import build_v17w2
        return jsonify(build_v17w2()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17W2","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False}}), 200


@app.get("/api/intelligence/v17x")
def v17x_route():
    try:
        from v17x import build_v17x
        return jsonify(build_v17x()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17X","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False}}), 200


@app.get("/api/intelligence/v17y")
def v17y_route():
    try:
        from v17y import build_v17y
        return jsonify(build_v17y()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17Y","error_type":type(e).__name__,"error":str(e)[:1200]}), 200


@app.get("/api/intelligence/v17z")
def v17z_route():
    try:
        from v17z import build_v17z
        return jsonify(build_v17z()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V17Z","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False}}), 200


@app.get("/api/intelligence/v18a")
def v18a_route():
    try:
        from v18a import build_v18a
        return jsonify(build_v18a()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18A","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,
                    "seller_intent_inferred":False,"seller_scoring":False}}), 200


@app.get("/api/intelligence/v18a1")
def v18a1_route():
    try:
        from v18a1 import build_v18a1
        return jsonify(build_v18a1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18A1","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False}}), 200


@app.get("/api/intelligence/v18b")
def v18b_route():
    try:
        from v18b import build_v18b
        return jsonify(build_v18b()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18B","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,"investigate_state_touched":False,
          "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18c")
def v18c_route():
    try:
        from v18c import build_v18c
        return jsonify(build_v18c()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18C","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,"investigate_state_touched":False,
          "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18d")
def v18d_route():
    try:
        from v18d import build_v18d
        return jsonify(build_v18d()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18D","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18e")
def v18e_route():
    try:
        from v18e import build_v18e
        return jsonify(build_v18e()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18E","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18f")
def v18f_route():
    try:
        from v18f import build_v18f
        return jsonify(build_v18f()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18F","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18g")
def v18g_route():
    try:
        from v18g import build_v18g
        return jsonify(build_v18g()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18G","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18h")
def v18h_route():
    try:
        from v18h import build_v18h
        return jsonify(build_v18h()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18H","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18h1")
def v18h1_route():
    try:
        from v18h1 import build_v18h1
        return jsonify(build_v18h1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18H1","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18i")
def v18i_route():
    try:
        from v18i import build_v18i
        return jsonify(build_v18i()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18I","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18j")
def v18j_route():
    try:
        from v18j import build_v18j
        return jsonify(build_v18j()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18J","error_type":type(e).__name__,"error":str(e)[:1200],
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
                    "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18k")
def v18k_route():
    try:
        from v18k import build_v18k
        return jsonify(build_v18k()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18K","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,
          "investigate_state_touched":False,"seller_intent_inferred":False,
          "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18k1")
def v18k1_route():
    try:
        from v18k1 import build_v18k1
        return jsonify(build_v18k1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18K1","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,
          "investigate_state_touched":False,"seller_intent_inferred":False,
          "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18l")
def v18l_route():
    try:
        from v18l import build_v18l
        return jsonify(build_v18l()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18L","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,
          "investigate_state_touched":False,"seller_intent_inferred":False,
          "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18m")
def v18m_route():
    try:
        from v18m import build_v18m
        return jsonify(build_v18m()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18M","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,
          "investigate_state_touched":False,"seller_intent_inferred":False,
          "seller_scoring":False,"overall_ranking":False}}), 200


@app.get("/api/intelligence/v18n")
def v18n_route():
    try:
        from v18n import build_v18n
        return jsonify(build_v18n()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18N","error_type":type(e).__name__,
          "error":str(e)[:1200],"guards":{"database_writes":False,
          "investigate_state_touched":False,"seller_intent_inferred":False,
          "seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v18o")
def v18o_route():
    try:
        from v18o import build_v18o
        return jsonify(build_v18o()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18O","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v18v")
def v18v_route():
    try:
        from v18v import build_v18v
        return jsonify(build_v18v()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18V","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v18w")
def v18w_route():
    try:
        from v18w import build_v18w
        return jsonify(build_v18w()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18W","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"external_calls":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v18x")
def v18x_route():
    try:
        from v18x import build_v18x
        return jsonify(build_v18x()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18X","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v18x1")
def v18x1_route():
    try:
        from v18x1 import build_v18x1
        return jsonify(build_v18x1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18X1","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v18y")
def v18y_route():
    try:
        from v18y import build_v18y
        return jsonify(build_v18y()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V18Y","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"external_calls":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v19a")
def v19a_route():
    try:
        from v19a import build_v19a
        return jsonify(build_v19a()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V19A","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"schema_introspection":False,"external_calls":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v19a1")
def v19a1_route():
    try:
        from v19a1 import build_v19a
        return jsonify(build_v19a()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V19A1","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"schema_introspection":False,"external_calls":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v19b")
def v19b_route():
    try:
        from v19b import build_v19b
        return jsonify(build_v19b()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V19B","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"external_calls":False,"schema_introspection":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v19b1")
def v19b1_route():
    try:
        from v19b1 import build_v19b
        return jsonify(build_v19b()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V19B1","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"external_calls":False,"schema_introspection":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/v19b2")
def v19b2_route():
    try:
        from v19b2 import build_v19b2
        return jsonify(build_v19b2()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"V19B2","error_type":type(e).__name__,"error":str(e)[:1200],"guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False}}), 200

@app.get("/api/intelligence/property-anomaly-lab-v1")
def property_anomaly_lab_v1_route():
    try:
        from property_anomaly_lab_v1 import build_property_anomaly_lab_v1
        return jsonify(build_property_anomaly_lab_v1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"PROPERTY_ANOMALY_LAB_V1","error_type":type(e).__name__,"error":str(e)[:1200],
                        "database_writes":0,"guards":{"database_writes":False,"external_calls":False,"schema_changes":False,
                        "investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,
                        "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
                        "contact_authorized":False,"outreach_touched":False}}), 200


@app.get("/api/intelligence/property-anomaly-lab-v1-1")
def api_property_anomaly_lab_v1_1():
    try:
        from property_anomaly_lab_v1_1 import build_property_anomaly_lab_v1_1
        return jsonify(build_property_anomaly_lab_v1_1())
    except Exception as e:
        return jsonify({
            "status":"error",
            "version":"PROPERTY_ANOMALY_LAB_V1_1",
            "error":str(e),
            "database_writes":0,
            "guards":{
                "database_writes":False,"external_calls":False,"schema_changes":False,
                "investigate_state_touched":False,"v19v_touched":False,
                "seller_qualification_changes":False,"seller_intent_inferred":False,
                "seller_scoring":False,"overall_ranking":False,
                "contact_authorized":False,"outreach_touched":False
            }
        }), 500

@app.get("/api/intelligence/property-anomaly-explainer-v1")
def api_property_anomaly_explainer_v1():
    try:
        from property_anomaly_explainer_v1 import build_property_anomaly_explainer_v1
        return jsonify(build_property_anomaly_explainer_v1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"PROPERTY_ANOMALY_EXPLAINER_V1","error_type":type(e).__name__,"error":str(e)[:1200],"database_writes":0,
            "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}), 200

@app.get("/api/intelligence/property-research-router-v1")
def api_property_research_router_v1():
    try:
        from property_research_router_v1 import build_property_research_router_v1
        return jsonify(build_property_research_router_v1()), 200
    except Exception as e:
        return jsonify({"status":"error","version":"PROPERTY_RESEARCH_ROUTER_V1","error_type":type(e).__name__,"error":str(e)[:1200],"database_writes":0,
            "guards":{"database_writes":False,"external_calls":False,"schema_changes":False,"investigate_state_touched":False,"v19v_touched":False,"seller_qualification_changes":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}), 200


@app.get("/api/intelligence/property-research-router-v1-1")
def api_property_research_router_v1_1():
    try:
        from property_research_router_v1 import build_property_research_router_v1
        return jsonify(build_property_research_router_v1()), 200
    except Exception as exc:
        return jsonify({"status":"error","version":"PROPERTY_RESEARCH_ROUTER_V1_1","error_type":type(exc).__name__,"error":str(exc)[:300],"database_writes":0,"guards":{"v19v_touched":False,"seller_qualification_changes":False,"contact_authorized":False}}), 500

@app.get("/api/intelligence/assessment-improvement-fact-resolution-v1")
def assessment_improvement_fact_resolution_v1_endpoint():
    try:
        from assessment_improvement_fact_resolution_v1 import build_assessment_improvement_fact_resolution_v1
        return build_assessment_improvement_fact_resolution_v1()
    except Exception as e:
        return {"status":"error","version":"ASSESSMENT_IMPROVEMENT_FACT_RESOLUTION_V1","error":str(e),"database_writes":0,"guards":{"database_writes":False,"v19v_touched":False,"contact_authorized":False,"outreach_touched":False}}

@app.get("/api/intelligence/targeted-property-assessment-lookup-v1")
def targeted_property_assessment_lookup_v1_endpoint():
    try:
        from targeted_property_assessment_lookup_v1 import build_targeted_property_assessment_lookup_v1
        return build_targeted_property_assessment_lookup_v1()
    except Exception as e:
        return {"status":"error","version":"TARGETED_PROPERTY_ASSESSMENT_LOOKUP_V1","error_type":type(e).__name__,"error":str(e)[:1200],"database_writes":0,"guards":{"database_writes":False,"external_calls":False,"v19v_touched":False,"contact_authorized":False,"outreach_touched":False}}

@app.get('/api/intelligence/property-form-peer-context-v1')
def property_form_peer_context_v1_endpoint():
    try:
        from property_form_peer_context_v1 import build_property_form_peer_context_v1
        return build_property_form_peer_context_v1()
    except Exception as e:
        return {'status':'error','version':'PROPERTY_FORM_PEER_CONTEXT_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/seasonal-residence-context-v1')
def seasonal_residence_context_v1_endpoint():
    try:
        from seasonal_residence_context_v1 import build_seasonal_residence_context_v1
        return build_seasonal_residence_context_v1()
    except Exception as e:
        return {'status':'error','version':'SEASONAL_RESIDENCE_CONTEXT_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/assessment-route-contextual-peer-scale-v1')
def assessment_route_contextual_peer_scale_v1_endpoint():
    try:
        from assessment_route_contextual_peer_scale_v1 import build_assessment_route_contextual_peer_scale_v1
        return build_assessment_route_contextual_peer_scale_v1()
    except Exception as e:
        return {'status':'error','version':'ASSESSMENT_ROUTE_CONTEXTUAL_PEER_SCALE_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/residential-class-semantics-v1')
def residential_class_semantics_v1_endpoint():
    try:
        from residential_class_semantics_v1 import build_residential_class_semantics_v1
        return build_residential_class_semantics_v1()
    except Exception as e:
        return {'status':'error','version':'RESIDENTIAL_CLASS_SEMANTICS_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/class-210-causal-resolution-v1')
def class_210_causal_resolution_v1_endpoint():
    try:
        from class_210_causal_resolution_v1 import build_class_210_causal_resolution_v1
        return build_class_210_causal_resolution_v1()
    except Exception as e:
        return {'status':'error','version':'CLASS_210_CAUSAL_RESOLUTION_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/class-210-causal-scale-v1')
def class_210_causal_scale_v1_endpoint():
    try:
        from class_210_causal_scale_v1 import build_class_210_causal_scale_v1
        return build_class_210_causal_scale_v1()
    except Exception as e:
        return {'status':'error','version':'CLASS_210_CAUSAL_SCALE_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/class-210-evidence-family-screen-v1')
def class_210_evidence_family_screen_v1_endpoint():
    try:
        from class_210_evidence_family_screen_v1 import build_class_210_evidence_family_screen_v1
        return build_class_210_evidence_family_screen_v1()
    except Exception as e:
        return {'status':'error','version':'CLASS_210_EVIDENCE_FAMILY_SCREEN_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/class-210-targeted-remainder-resolution-v1')
def class_210_targeted_remainder_resolution_v1_endpoint():
    try:
        from class_210_targeted_remainder_resolution_v1 import build_class_210_targeted_remainder_resolution_v1
        return build_class_210_targeted_remainder_resolution_v1()
    except Exception as e:
        return {'status':'error','version':'CLASS_210_TARGETED_REMAINDER_RESOLUTION_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/class-210-counterexample-causal-family-v1')
def class_210_counterexample_causal_family_v1_endpoint():
    try:
        from class_210_counterexample_causal_family_v1 import build_class_210_counterexample_causal_family_v1
        return build_class_210_counterexample_causal_family_v1()
    except Exception as e:
        return {'status':'error','version':'CLASS_210_COUNTEREXAMPLE_CAUSAL_FAMILY_V1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/c210-close1')
def c210_close1_endpoint():
    try:
        from c210_close1 import build_c210_close1
        return build_c210_close1()
    except Exception as e:
        return {'status':'error','version':'C210_CLOSE1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/find1')
def find1_endpoint():
    try:
        from find1 import build_find1
        return build_find1()
    except Exception as e:
        return {'status':'error','version':'FIND1','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'v19v_touched':False,'contact_authorized':False,'outreach_touched':False}}

@app.get('/api/intelligence/find2')
def find2_endpoint():
    try:
        from find2 import build_find2
        return jsonify(build_find2()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND2','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200

@app.get('/api/intelligence/find3')
def find3_endpoint():
    try:
        from find3 import build_find3
        return jsonify(build_find3()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND3','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200

@app.get('/api/intelligence/find4')
def find4_endpoint():
    try:
        from find4 import build_find4
        return jsonify(build_find4()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND4','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':False,'schema_changes':False,'investigate_state_touched':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False,'closed_class_210_routes_reopened':False}}), 200


@app.get('/api/intelligence/find5')
def find5_endpoint():
    try:
        from find5 import build_find5
        return jsonify(build_find5()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND5','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200


@app.get('/api/intelligence/find6')
def find6_endpoint():
    try:
        from find6 import build_find6
        return jsonify(build_find6()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND6','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200


@app.get('/api/intelligence/find7')
def find7_endpoint():
    try:
        from find7 import build_find7
        return jsonify(build_find7()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND7','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200


@app.get('/api/intelligence/find8')
def find8_endpoint():
    try:
        from find8 import build_find8
        return jsonify(build_find8()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND8','error_type':type(e).__name__,'error':str(e)}), 500

@app.get('/api/intelligence/find9')
def find9_endpoint():
    try:
        from find9 import build_find9
        return jsonify(build_find9()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND9','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200


@app.get('/api/intelligence/find10')
def find10_endpoint():
    try:
        from find10 import build_find10
        return jsonify(build_find10()), 200
    except Exception as e:
        return jsonify({'status':'error','version':'FIND10','error_type':type(e).__name__,'error':str(e)[:1200],'database_writes':0,'guards':{'database_writes':False,'external_calls':True,'external_calls_read_only':True,'schema_changes':False,'v19v_touched':False,'seller_qualification_changes':False,'seller_intent_inferred':False,'seller_scoring':False,'overall_ranking':False,'contact_authorized':False,'outreach_touched':False}}), 200
