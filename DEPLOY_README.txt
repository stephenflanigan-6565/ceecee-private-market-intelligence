CANONICAL NAME: API Intelligence Property Anomaly Explainer v1

PURPOSE
Explain/kill the 87 A4 land-vs-improvement assessment anomalies found by Property Anomaly Lab v1.1 using existing physical-property context before any new source or human review.

CHANGED FILES ONLY
1. web_app.py
2. property_anomaly_explainer_v1.py

ENDPOINT
/api/intelligence/property-anomaly-explainer-v1

GUARDS
READ ONLY. No DB writes. No V19V changes. No seller qualification/scoring. No contact/outreach authority. Missing information is nonblocking. NEEDS_CEECEE_VERIFICATION is an allowed research disposition for worthwhile cases that cannot be resolved automatically; it is not contact authorization.
