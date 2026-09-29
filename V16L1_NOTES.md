# V16L1 — Route Registration Repair

Protected baseline: V16K1 operations console.
Scope: repair only V16L route registration against the proven V16K web application entry point.
Files to replace/add: `web_app.py`, `title_transfer_event_intelligence_v16l.py`.
No database writes. No seller scoring. No INVESTIGATE state changes. No outreach.
Expected endpoint: `/api/intelligence/title-transfer-event-intelligence-v16l`.
Rollback: restore prior `web_app.py` and remove `title_transfer_event_intelligence_v16l.py`.
