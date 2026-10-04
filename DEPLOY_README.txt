PMI PROPERTY ANOMALY LAB V1 — ISOLATED READ-ONLY TEST

Donor inspected: uploaded V19B2 package, preserving its additive-route pattern.
Files changed/added:
1. property_anomaly_lab_v1.py — NEW
2. web_app.py — V19B2 web_app plus one additive lazy-import route

Endpoint after deployment:
/api/intelligence/property-anomaly-lab-v1

Expected guards:
database_writes = 0
v19v_touched = false
seller_qualification_changes = false
seller_scoring = false
external_calls = false
contact_authorized = false
outreach_touched = false

This test reads current PROPERTY_CONTEXT and ASSESSMENT_CONTEXT payloads from evidence_ledger, reports actual payload-field coverage, and runs only anomaly families supported by discovered evidence.

DO NOT delete other repository files. Add the new module and replace web_app.py only if the live repository matches this donor lineage.
Return the endpoint JSON to ChatGPT for PASS/FAIL analysis.
