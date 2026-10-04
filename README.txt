PMI FIND8S — ESRI INTERSECT GEOMETRY CONTRACT REPAIR

FIND8/FIND8R safely resolved all target parcel geometries but GeometryServer rejected every intersection.
Root cause isolated against Esri REST documentation: the single `geometry` argument must be wrapped as
{geometryType: esriGeometryPolygon, geometry: {...}}. FIND8R sent the raw polygon.

FIND8S changes only that contract. Same 20 targeted multi-zone/conservation parcels, same authoritative
Town parcel and zoning sources, same area accounting and interpretation guards.

No writes, scoring, ranking, seller-intent inference, contact authorization, outreach, schema changes,
or V19V modification. Zone shares are geometric facts only and never establish lawful use, buildability,
subdivision yield, setbacks, economics, or entitlement.

Endpoint: /api/intelligence/find8
