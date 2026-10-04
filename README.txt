PMI FIND5D — SCTM PARCEL → ZONING TRANSPORT REPAIR

FIND5C proved exact 19-digit SCTM identity for all 12 validation parcels and resolved
zoning for 9. Three parcels failed only during the geometry-bearing zoning request
with HTTP 404.

FIND5D changes one thing:
- zoning spatial-intersection request uses form-encoded HTTP POST instead of GET.

Unchanged:
- exact SCTM parcel identity
- deterministic 12-property validation sample
- zoning layer and spatial relationship
- FIND4/FIND3 logic and route states
- no seller intent, scoring, ranking, contact, outreach, writes, or V19V changes
- missing/failed zoning evidence remains UNKNOWN, never property rejection
- zoning does not imply entitlement, subdivision permission, or redevelopment approval

Endpoint: /api/intelligence/find5
