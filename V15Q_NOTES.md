# V15Q — Candidate Research Cohort Preview

Purpose: turn the proven Westhampton Beach population measurements into an auditable property-level research preview without creating seller scores, WATCH/INVESTIGATE states, opportunities, or outreach.

Architecture rule: BUILD ONCE — CONFIGURE BY MARKET — MEASURE LOCALLY. Westhampton Beach is Pilot 01. Dune Road is one configured local corridor only and is never required for candidate inclusion. Future markets replace/add local configuration without rewriting the core cohort engine.

All 2,082 proven residential-side parcels are evaluated. Cohorts overlap. Each returned member includes parcel/address, factual cohort, latest recorded transfer date/age, transfer-history depth, ownership-evidence count, property age, acreage, living area, and explicit factual reason codes.

Research cohort lenses in V15Q:
- DUNE_ROAD_HISTORY_RESEARCH: configured corridor + latest recorded transfer 10y+
- SEASONAL_RESIDENTIAL_HISTORY_RESEARCH: land-use 260 + latest recorded transfer 20y+
- VACANT_RESIDENTIAL_LAND_HISTORY_RESEARCH: persisted residential-vacant cohort + latest recorded transfer 20y+
- LARGER_LOT_HISTORY_RESEARCH: acreage 1+ + latest recorded transfer 20y+
- LARGER_IMPROVEMENT_HISTORY_RESEARCH: living area 2,500+ sqft + latest recorded transfer 20y+
- GENERAL_IMPROVED_HISTORY_RESEARCH: improved residential + latest recorded transfer 20y+ + property age 25y+ + 3+ transfer-history records

These are research lenses, not promoted rules. No ranking or seller probability is produced.

Safety: READ ONLY. Zero database writes. Zero seller scoring. Zero signals/events. Zero opportunity mutation. Zero outreach.

Endpoint: /api/westhampton-universe/candidate-research-cohorts-v15q
