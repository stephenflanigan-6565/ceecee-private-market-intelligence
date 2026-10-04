PMI FIND10 — Targeted Property-Form Fact Test

Purpose
- Continue from promoted FIND9 property-intelligence chassis.
- Query ONE already-available authoritative Town parcel field (PROP_TYPE).
- Scope ONLY to existing FIND9 TARGETED_FACT_REQUIRED cases.

Decision boundary
- This is not generic enrichment and does not open a new data hunt.
- A returned PROP_TYPE is one property-form fact only.
- It does not prove vacancy, buildability, entitlement, lawful use, or seller intent.
- Missing/ambiguous data does not hold PMI back. If the fact is material and still unresolved,
  retain the targeted/human-verification need; otherwise continue.

Endpoint
/api/intelligence/find10

Protected
- FIND9 logic preserved.
- V19V untouched.
- No writes, scoring, ranking, seller qualification, contact, or outreach.
