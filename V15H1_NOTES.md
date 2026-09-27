# V15H1 — Canonical Lookup Schema Repair

## Scope
Single-problem repair only. The V15H diagnostic proved the new ownership/transfer adapter path failed before any Suffolk request because it queried a nonexistent `properties.active` column.

## Change
Replaced the invalid canonical parcel filter `active=1` with the proven canonical source-status filter `status='A'` in the two shared parcel-selection helpers in `ownership_transfer_probe.py`.

## Protected systems
- No PostgreSQL schema change.
- No database writes.
- No property, ownership, transfer, signal, opportunity, scoring, Contact Governor, or outreach mutation.
- V14/V15B1/V15E proven foundation remains unchanged.

## Verification target
Redeploy, then rerun `/api/westhampton-universe/internal-failure-isolation-v15h`. Expected result: canonical lookup succeeds and the diagnostic proceeds to PARCEL_CONTROL, OWNER, and TRANSFER_HISTORY tests.

LOCK → CHANGE → VERIFY → STOP.
