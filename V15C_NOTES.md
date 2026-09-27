# V15C — Westhampton Canonical Universe Composition Profile

## Protected baseline
V15B1 — canonical universe + normalized comparison repair. Proven live against PostgreSQL:
2,545 fetched / 2,545 canonical / 0 inserted / 0 updated / 2,545 unchanged / 0 snapshots added.

## One problem
Before classifying the Westhampton universe, inspect the actual land-use composition and field completeness stored in canonical PostgreSQL memory. Do not invent classification rules from assumptions about Suffolk land-use codes.

## Allowed change
- Add `universe_profile.py`.
- Add one read-only route to `web_app.py`: `/api/westhampton-universe/profile-v15c`.

## Protected systems
- V15B1 collector/change detection unchanged.
- No canonical property writes.
- No owner/transfer ingestion.
- No signals/opportunities.
- No Mojo/legacy data.
- No paid data.
- Outreach remains OFF.

## Verification gate
Live endpoint must report:
- PostgreSQL backend.
- canonical_active_parcels = 2545 unless the locked collector has independently observed a legitimate source change.
- land-use distribution totals equal canonical active parcels.
- municipality distribution totals equal canonical active parcels.
- field completeness counts.
- database_writes = 0.
- classification_applied = false.

Only after this profile is inspected may residential/non-residential classification rules be designed.
