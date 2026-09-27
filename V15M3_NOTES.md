# V15M3 — Assessment Value Field Diagnostic

Purpose: isolate why the persisted 2025 assessment layer has 2,082 residential records but V15M reports zero positive full-market values.

Change only: read-only diagnostics for persisted `full_market_value`, `assessed_total`, and `assessed_land` null/zero/positive coverage. The proven V15M2 residential cohort source remains unchanged.

No schema changes. No database writes. No seller scoring, signals, events, opportunities, or outreach.

This is diagnostic only. It does not substitute assessed value for market value and does not alter V15L evidence.
