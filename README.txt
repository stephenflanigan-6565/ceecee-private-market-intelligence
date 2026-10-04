PMI FIND5C — LIVE-CONTRACT SCTM PARCEL → WESTHAMPTON BEACH ZONING VALIDATION

Purpose
Validate the Town GIS join on a deterministic 12-property FIND4 land-route cross-section.

Repair from FIND5/FIND5R
FIND5P proved the live Tax Parcels layer exposes SCTM as a string and showed a sample
19-digit SCTM in the same Suffolk identifier family used by PMI. FIND5C therefore uses
only exact SCTM='<PMI parcel_id>' for parcel identity. Address is cross-check only.

Then:
1. return authoritative Town parcel geometry;
2. spatially intersect that geometry with LandManager layer 41 (Westhampton Beach);
3. report zoning CODE / ZONE / DESCRIPT where present.

Safety
Read only. No database writes. No seller scoring/ranking/intent. No contact/outreach.
No route is rejected because a source match is missing. Zoning is evidence only and
does not prove subdivision, redevelopment permission, entitlement, or economics.
V19V remains untouched.

Live endpoint
/api/intelligence/find5

Pass signal
A meaningful portion of the validation sample returns PARCEL_AND_ZONING_RESOLVED.
NO_SCTM_MATCH remains UNKNOWN and is not a property rejection.
