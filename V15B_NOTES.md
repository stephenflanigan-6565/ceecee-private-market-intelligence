# V15B — Westhampton Canonical Universe Population

Protected parent: V15A Westhampton Universe Source Probe — PASS (2,545 fetched / 2,545 unique / zero validation defects).

## One allowed change
Promote the already-validated Suffolk County TaxParcelPolygon Westhampton Beach active-parcel universe into canonical PostgreSQL property memory.

## Writes allowed
- `properties`: insert/update canonical parcel facts; refresh `last_seen_at`.
- `snapshots`: append only when the official source payload is new; identical payloads deduplicate by existing unique key.
- `source_runs`: audit each population run.

## Explicitly untouched
- owners / transfers / transfer parties
- signals / opportunities / contact governor
- buyer requirements / legacy relationships / Mojo
- paid enrichment
- homeowner outreach

## Verification gate
First live run should reconcile source records to canonical active district 0905 parcels. A second identical run must create zero duplicate properties; expected behavior is inserted=0, updated=0, unchanged≈source count, snapshots_added=0 unless Suffolk changed between runs.

Do not advance to ownership/history until this gate passes.
