# V15D — Westhampton Factual Cohort Classification Preview

## Scope
Read-only preview of factual property-use cohorts derived from the raw official `LANDUSE` code already stored in the locked Westhampton canonical universe.

No seller scoring. No opportunity creation. No ownership work. No outreach. No database writes.

## Why this gate exists
V15C proved the 2,545-parcel universe contains multiple property-use classes and 172 missing `LANDUSE` values. V15D previews a reversible segmentation before any classification is persisted.

## Proposed cohorts
- `RESIDENTIAL_IMPROVED` — 2xx residential codes.
- `RESIDENTIAL_VACANT_LAND` — selected 3xx residential/rural vacant codes: 310, 311, 312, 314, 315, 320, 321, 322, 323.
- `COMMERCIAL_MIXED` — commercial vacant 330/331 plus 4xx commercial.
- `COMMUNITY_PUBLIC_UTILITY` — utility vacant 380 plus 6xx community services and 8xx public services.
- `OTHER_NON_TARGET` — industrial vacant 340/341 plus 5xx recreation, 7xx industrial, 9xx conservation/public-park family.
- `UNRESOLVED` — missing or any code not explicitly mapped.

Raw `LANDUSE` is preserved and remains the source evidence. Cohort is interpretation only.

## Verification gate
Endpoint: `/api/westhampton-universe/classification-preview-v15d`

Pass requirements:
1. `canonical_active_parcels` = 2545 unless the official universe has legitimately changed.
2. `cohort_total` equals `canonical_active_parcels`.
3. No database writes.
4. No property/opportunity/outreach data touched.
5. Review unresolved codes before any cohort is persisted.
