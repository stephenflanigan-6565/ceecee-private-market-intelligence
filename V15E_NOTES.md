# V15E — Westhampton Factual Cohort Persistence

## Scope
Persist only the V15D-verified factual property-use cohorts for the 2,545 active Westhampton Beach parcels.

## Design
- Separate `property_classifications` table: raw Suffolk `LANDUSE` on `properties` is not overwritten.
- Derived cohort is reversible and carries `method_version` provenance.
- First run should insert 2,545 classifications.
- Immediate second run should insert 0, update 0, unchanged 2,545.
- Missing LANDUSE remains `UNRESOLVED`.

## Protected systems
No seller scoring, opportunity state, ownership, transfer history, outreach, or contact governor changes.

## Verification gate
Expected first run: persisted_active_classifications=2545 and cohort counts exactly match V15D preview.
Expected second run: inserted=0, updated=0, unchanged=2545.
