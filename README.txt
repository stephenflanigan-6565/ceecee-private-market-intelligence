PMI FIND8R — GeometryServer Contract Repair

FIND8 proved all 20 target parcels and parcel areas resolve, but all remote polygon
intersections failed with ArcGIS "Syntax error in JSON geometry representation".

FIND8R changes one thing only:
- embeds spatialReference {wkid:2263} directly in BOTH polygon geometries sent to
  GeometryServer/intersect, while retaining sr=2263 at the operation level.

The same 20 FIND7 multi-zone/conservation targets are rerun. Service errors are
preserved verbatim. No FIND7 route/state logic changes. No writes, scoring, ranking,
seller intent, contact, outreach, entitlement, buildability, subdivision-yield, or
V19V changes.

Endpoint: /api/intelligence/find8
