# V15K2 — NYS ORPTS Assessment/Value Source Probe

## Problem isolated
V15K/V15K1 proved that live DigitalOcean requests to the 343-page Southampton 2026 PDF are an unreliable transport dependency. Both failures occurred before parsing/join/database writes.

## Surgical architecture change
V15K2 replaces only the assessment acquisition source for the coverage probe. It queries the public NYS ITS Tax Parcels Feature Service. NYS documents that the service's county attributes are populated from ORPTS assessment-roll tabular data and that Suffolk County permits public redistribution.

The public state layer currently contains 2025 assessment-roll attributes. That is sufficient to establish the machine-readable assessment/value memory path now. The Southampton 2026 roll remains a later annual snapshot enrichment and is not discarded.

## Fields measured
- SWIS / SBL / PRINT_KEY join identifiers
- property class
- acreage
- assessed land
- assessed total
- full market value
- year built
- living square feet
- bedrooms / full baths

## Safety
READ ONLY. Zero assessment persistence, seller scoring, signals, opportunities, events, or outreach.

## Existing route intentionally preserved
`/api/westhampton-universe/assessment-probe-v15k`

The JSON version/mode reports V15K2.
