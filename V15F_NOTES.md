# V15F — Westhampton Ownership + Current Transfer Coverage Probe

Purpose: measure the official Suffolk ownership and current-transfer coverage against the locked 2,545-parcel Westhampton Beach canonical universe before any ownership/history data is persisted.

## Scope
- READ ONLY.
- Queries official Suffolk `TaxParcelOwner` and `TaxParcelTransferCurrent` services for parcel IDs beginning `0905`.
- Intersects source results with the existing canonical active Westhampton parcel IDs in PostgreSQL.
- Reports coverage, missing-record counts, and parcel-ID-only diagnostic samples.
- Does **not** expose owner names through the public diagnostic endpoint.

## Protected systems
- No database writes.
- No ownership persistence.
- No transfer persistence.
- No seller scoring.
- No opportunities.
- No outreach.

## Promotion gate
Use live results to validate source reachability and coverage. Do not build/persist ownership or transfer history until this probe is reviewed.
