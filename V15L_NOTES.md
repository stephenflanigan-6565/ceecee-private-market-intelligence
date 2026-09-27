# V15L — Assessment / Value Evidence Persistence

Purpose: persist only the 2,490 exact, collision-free current-canonical ↔ 2025 NYS ORPTS assessment matches proven by V15K7/V15K8.

Controls:
- canonical count must equal 2,545
- canonical normalized keys must be unique/non-null
- state normalized keys must have no duplicates
- exact proven matched count must equal 2,490
- roll year must equal 2025
- 55 residual parcels receive no fabricated assessment record
- no seller scoring, signals, events, opportunities, or outreach
- transaction rolls back on failure

New table: `assessment_evidence`, keyed by `(parcel_id, source, roll_year)`.

Route: `/api/westhampton-universe/assessment-persist-v15l`

Verification: run once for persistence, inspect counts, then run again for idempotency (expected inserted=0, updated=0, unchanged=2490 if source is unchanged).
