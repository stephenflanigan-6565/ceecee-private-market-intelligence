# V16C — Factual Evidence Interpretation + Opportunity Pathways

## Protected baselines
- V16A persistent evidence memory: PROVEN / LOCKED (18,001 rows; second pass 0 inserts / 18,001 known).
- V16B change detection: PROVEN / LOCKED (second pass 18,001 unchanged; 0 change events).

## Allowed change
Add a market-agnostic interpretation layer that consumes V16B current state/change events and emits explainable research pathways. It does not infer seller intent, rank sellers, set WATCH/INVESTIGATE, authorize contact, or mutate source/evidence/change tables.

## Purpose
Bridge factual evidence memory to the first operational investigation queue. Westhampton Beach remains Pilot 01 only; core pathway code consumes market membership and is designed for Suffolk County multi-market operation.

## Route
`GET /api/intelligence/opportunity-pathways-v16c`

## Important limits
- Transfer gap is not owner tenure.
- Research pathway is not seller intent or probability.
- Price, luxury, property size, and geographic prestige are not eligibility gates.
- All market residential properties remain eligible even with no current pathway.
- V16B factual changes are an independent operational pathway once future refreshes detect them.

## Next gate
Verify V16C live output, then V16D may create the operational INVESTIGATE state/queue with explicit explanations and downstream ownership/contact safeguards.
