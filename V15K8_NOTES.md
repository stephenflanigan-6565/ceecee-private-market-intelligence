# V15K8 — Parcel Lineage Residual Diagnostic

Purpose: classify the 55 canonical parcels and 10 NYS assessment keys left unmatched after V15K7 without changing the proven parser or forcing matches.

- Preserves V15K7 normalization and raw-SBL parser.
- Queries official Suffolk current and historic parcel layers read-only.
- Uses exact normalized S/B/L plus Suffolk CREATEDATE/LASTUPDATE for bounded residual classification.
- Does NOT infer parent/child lineage from geometry.
- Does NOT persist assessment data.
- Does NOT touch seller scoring, signals, opportunities, or outreach.

Expected route remains `/api/westhampton-universe/assessment-probe-v15k`.
