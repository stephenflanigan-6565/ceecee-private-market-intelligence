# V15B1 — Canonical Comparison Normalization Repair

## Protected baseline
V15B successfully populated 2,545 unique active Westhampton Beach parcels into PostgreSQL with zero duplicate properties and zero duplicate snapshots on the immediate second run.

## Observed failure
The immediate second population run incorrectly reported `updated: 2545` and `unchanged: 0`, even though snapshot deduplication correctly reported `snapshots_added: 0`.

## Root cause
The collector compared raw ArcGIS values directly with PostgreSQL-returned values. Several canonical columns are stored as TEXT while ArcGIS may emit numeric-looking values as numbers. PostgreSQL therefore returned string representations that were semantically identical but type-unequal to the raw source values, producing false updates.

## Allowed change
Normalize incoming values to the exact canonical storage types before both comparison and write. No schema change. No new data source. No signal/opportunity logic. No outreach.

## Verification gate
Run the existing V15B population endpoint once after deployment. Required result for an unchanged Suffolk source universe:
- records_fetched: 2545 (subject only to legitimate source change)
- inserted: 0
- updated: 0
- unchanged: records_fetched
- snapshots_added: 0
- canonical_active_parcels: 2545 (subject only to legitimate source change)
- outreach_touched: false
- opportunity_data_touched: false

If the official source genuinely changed between runs, investigate only the changed count rather than forcing the historical 2,545 count.
