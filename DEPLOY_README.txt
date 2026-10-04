Canonical name: API Intelligence Assessment Improvement Fact Resolution v1

Purpose:
Apply the locked source-semantics consumption rules to the 24 cases routed to VERIFY_IMPROVEMENT_AND_ASSESSMENT_SEMANTICS. This is a read-only kill/strengthen handoff, not a seller score and not marketing.

Endpoint:
/api/intelligence/assessment-improvement-fact-resolution-v1

Expected live reconciliation:
- expected_target_cases: 24
- target_cases_received: 24
- cases_resolved: 24
- unique_target_parcels: 24
- duplicate_target_parcels: []
- all_target_cases_accounted_for: true

Protected rules:
- full_market_value is prohibited as opportunity evidence in the current dataset because it is zero population-wide.
- assessed_total and assessed_land are assessment components, not market price.
- zero full baths is a plausibility warning only.
- property class may group peers without inventing class-code semantics.
- no seller-intent inference, score/rank, outreach/contact authority, schema changes, database writes, or V19V changes.

Forward contract:
Each case preserves property identity, WHY PMI found it, consumable evidence, excluded/contradictory data-quality evidence, material unknown, and one next fact. Future owner/property enrichment and marketing-relevant characteristics remain separate and evidence-gated.
