PMI FIND3 — Full-Population Causal Triage Repair

Deploy only these files together:
- find2.py
- find3.py
- web_app.py

Endpoint:
/api/intelligence/find3

Purpose:
- FIND2 still evaluates the full WHB residential universe and keeps its operator endpoint compact.
- FIND3 now requests FIND2's complete in-memory candidate population and causally triages every discovered land/property-utilization candidate before any display sampling.
- FIND3 endpoint returns full coverage/state/family counts plus deterministic examples (up to 3 per causal family), avoiding a giant operator payload.
- A future FIND integration may call build_find3(include_all_profiles=True) for the complete machine handoff.

Expected live proof:
- scope.find2_whole_market_candidate_count = 153 (assuming unchanged data)
- scope.triaged_candidate_count = 153
- scope.complete_population_coverage = true
- summary.coverage_complete = true
- profile_payload.complete = false on the public endpoint by design; this refers only to display sampling, not triage coverage.

Guards:
READ ONLY. No writes, schema changes, seller scoring/ranking/intent, contact authorization, outreach, investigation-state changes, V19V changes, or reopening of closed Class-210 assessment routes.
