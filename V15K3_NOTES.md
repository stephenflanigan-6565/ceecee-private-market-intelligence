# V15K3 — Canonical S/B/L Normalization Repair

## Problem isolated by V15K2
V15K2 successfully reached the NYS ORPTS source and fetched assessment/value data, but matched 0 canonical parcels. Its diagnostic samples proved a deterministic representation mismatch, not a source or database failure:

- canonical `100-100-1001` corresponds to ORPTS `1-1-1.001`
- canonical `1000-100-1000` corresponds to ORPTS `10-1-1`

The canonical property table stores Suffolk section/block/lot in fixed-width scaled integer form.

## Allowed change
Decode canonical components only for this assessment join:
- section / 100
- block / 1000
- lot / 1000

ORPTS SBL/PRINT_KEY parsing is unchanged. Database schema, persistence, ownership, transfers, signals, opportunities, scoring, and outreach are untouched.

## Test objective
Re-run the existing read-only route:
`/api/westhampton-universe/assessment-probe-v15k`

Expected result: non-zero/high canonical match coverage. Do not persist assessment data yet.
