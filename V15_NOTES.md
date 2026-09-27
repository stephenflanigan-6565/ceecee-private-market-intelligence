# V15A — Westhampton Beach Universe Source Probe

## Protected baseline
V14 Cloud Memory Persistence Test remains the protected cloud foundation.

## One allowed change
Add a read-only probe for the official Suffolk County TaxParcelPolygon source so the proposed Westhampton Beach parcel filter can be validated in the live DigitalOcean environment before any property records are written.

## Filter under test
`DISTRICT = '0905' AND STATUS = 'A'`

## What V15A does
- Queries the official Suffolk County TaxParcelPolygon feature layer.
- Pages results using the service's supported pagination.
- Counts fetched and unique parcel IDs.
- Reject-checks missing parcel IDs, wrong district, wrong status, and duplicate parcel IDs.
- Returns five sample parcel/address rows for human sanity checking.

## What V15A does NOT do
- No PostgreSQL property writes.
- No owner collection.
- No transfer collection.
- No seller scoring.
- No opportunity-state changes.
- No outreach.
- No paid data.

## Promotion gate
Do not enable the write/bootstrap collector until the live probe returns a nonzero, internally consistent universe and the sample rows are visibly Westhampton Beach.
