# V15V — Property / Parcel Change Event Evidence Rail

READ ONLY. Evaluates all 2,082 persisted residential-side parcels and inventories actual dated change evidence already available from authorized persisted sources.

## Allowed change
Add one independent factual evidence rail for property/parcel change events. Do not modify V15S guard logic, V15T universal eligibility, V15U market-exposure readiness, seller scoring, WATCH/INVESTIGATE, opportunities, or outreach.

## Evidence rules
- Transfer/title dates enter only through the V15S quality guard.
- Parcel source-created and source-last-update dates are reported as metadata, not assumed physical property changes or seller intent.
- Assessment change is not claimed unless at least two comparable roll years exist.
- Static acreage, size, age, value, land use, and geography never become change events.
- A factual event can justify research; it does not authorize contact.

## Endpoint
`/api/westhampton-universe/property-parcel-change-events-v15v`
