# V15W — Permit / Building-Change Source Readiness

Read-only gate before connecting Southampton permit/certificate/building-change evidence.

## Purpose
- Preserve the proven V15V property/parcel change rail.
- Confirm the source/evidence contract without pretending permit history is already connected.
- Keep all 2,082 residential-side parcels eligible.
- Require authorized access and an auditable parcel match before persistence.

## Official source findings used for this gate
Town of Southampton official materials document that GIS ePortal contains permits, certificates of occupancy/compliance, sales, mass appraisal and scanned property documents. The Town also exposes a public permit/property lookup, but V15W does not claim that lookup is approved or technically suitable for bulk automated ingestion. Residential Building Department forms establish useful activity vocabulary including additions, new dwellings, renovations, demolitions and pools/spas/hot tubs.

## Hard boundaries
No database writes. No permit events are invented. No seller score. No WATCH/INVESTIGATE mutation. No outreach. Permit application/issuance does not equal completed work, and permit activity does not equal seller intent.

## Route
`/api/westhampton-universe/permit-building-change-source-readiness-v15w`
