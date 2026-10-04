PMI FIND5P — GIS SOURCE CONTRACT PROBE

Purpose
- Diagnose the live Town of Southampton ArcGIS parcel/zoning layer schema and query behavior.
- This is the isolated repair checkpoint after FIND5R proved all attempted TAXMAP/GV_TAXMAP/DSBL/SCTM queries were rejected.

Endpoint
/api/intelligence/find5-probe

Safety
- READ ONLY external GIS calls.
- Zero database writes.
- Zero FIND route decisions or changes.
- No seller scoring/ranking/intent/contact/outreach.
- V19V untouched.

Acceptance
- Parcel metadata returns live field names/types and capabilities, OR an explicit ArcGIS/HTTP error.
- A harmless where=1=1 sample query returns one feature schema, OR an explicit error.
- Controlled TAXMAP query returns its exact ArcGIS error or valid response.
- Do not scale or modify FIND routes from this probe.
