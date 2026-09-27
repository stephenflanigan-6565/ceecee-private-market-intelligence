# V15K — Assessment / Value Intelligence Source Probe

## Scope
One problem only: prove that the official Town of Southampton 2026 Westhampton Beach assessment roll (SWIS 473607) can be extracted and joined reliably to the locked Suffolk canonical Westhampton universe.

## Safety boundary
- READ ONLY.
- No assessment persistence.
- No seller scoring.
- No opportunities.
- No outreach.
- Canonical guard requires exactly 2,545 active district 0905 parcels before the probe proceeds.

## Source
Town of Southampton 2026 Assessment Roll — Westhampton Beach, SWIS 473607.

## Join method
The roll's Suffolk County tax-map section/block/lot components are normalized numerically and matched to the existing canonical `properties.section`, `properties.block`, and `properties.lot` components. V15K measures coverage and reports mismatches; it does not guess or write unresolved matches.

## Exact route
`/api/westhampton-universe/assessment-probe-v15k`

## Expected next gate
If extraction and canonical match coverage are strong, inspect any mismatch class before creating the separate V15L assessment/value persistence layer.
