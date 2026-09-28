# V16E1 — Suffolk Source Access Isolation Repair

Protected baseline: V16D.

Failure under test: V16E received HTTP 403 during source acquisition.

Allowed change: acquisition diagnostics only.

This build performs eight read-only probes: FeatureServer and MapServer query endpoints for Owner and Transfer History, each over GET and POST. Every probe requests only `returnCountOnly=true`. It records HTTP status and ArcGIS response behavior.

Hard guard: V16E1 performs zero database writes. It does not refresh evidence, infer seller intent, score properties, authorize contact, or touch outreach.

Promotion rule: do not build the live refresh on any path until V16E1 proves that exact official path works from the deployed runtime.
