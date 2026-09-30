# V16S — Temporal Relevance Cleanup

Status: isolated deployment test. Do not promote until live JSON is inspected.

Protected baseline: V16R1 factual deeper-research resolution.

Change scope:
- Adds `temporal_relevance_cleanup_v16s.py`.
- Registers `/api/intelligence/temporal-relevance-cleanup-v16s` in `web_app.py`.
- No database writes, seller scoring, INVESTIGATE mutation, contact authorization, or outreach.

Temporal bands:
- SAME_DAY
- LE_365_DAYS
- 366_DAYS_TO_3_YEARS
- HISTORICAL_ONLY (>3 years)

Historical facts are retained; only their current research weight is cleaned.
