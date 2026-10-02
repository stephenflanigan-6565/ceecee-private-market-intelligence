# V17E2 — Route Registration Probe Only

Purpose: isolate DigitalOcean/Flask route registration from V17E intelligence logic.

Deployment:
- Replace ONLY web_app.py.
- Do NOT deploy persistent_evidence_reevaluation_v17e.py.
- Baseline is exact proven V17D web_app.py plus one static GET route.

Endpoint:
`/api/intelligence/v17e2-route-probe`

Expected:
- status=ok
- version=V17E2
- mode=ROUTE_REGISTRATION_PROBE_ONLY
- intelligence_logic_loaded=false
- database_access=false
- database_writes=false

This test does not read or write PMI evidence.
