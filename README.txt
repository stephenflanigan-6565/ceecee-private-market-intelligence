PMI FIND18
==========
Purpose: read-only existing-evidence site-use branching experiment.

Tests only the FIND17 supported vacant/minimally-improved property-form cases.
Reuses already-resolved Town zoning/site-use memory. Makes no new external lookup.
Branches property reasoning into residential infill, specialized/HBU, or unknown.
Does NOT infer entitlement, buildability, seller intent, or contact authorization.
Does NOT interpret DIM_REG beyond preserving the observed zoning attribute.
V19V remains untouched.

Endpoint: /api/intelligence/find18
