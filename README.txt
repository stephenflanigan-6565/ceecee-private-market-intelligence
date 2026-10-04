PMI FIND3 — Land/Property Causal Triage
Endpoint: /api/intelligence/find3

Deploy these three files together:
- find2.py (required FIND3 dependency; unchanged FIND2 discovery rail)
- find3.py (new causal triage layer)
- web_app.py (adds FIND3 endpoint)

READ ONLY. No database writes. No seller scoring/ranking. No seller intent inference.
No outreach/contact authorization. V19V untouched. Closed Class-210 routes stay closed.

Purpose:
- preserve why PMI noticed a land/property relationship
- distinguish corroborated relationships from data/property-form conflicts
- never treat zero improvement or missing/zero living-area as vacancy proof
- require explanatory evidence for causal route closure
- retain NEEDS_TARGETED_FACT as a valid state

Important scope: FIND2 currently exposes 40 diagnostic candidate records in its payload even though
whole-market discovery found 153. FIND3 truthfully triages those 40 only. If live verification passes,
the next build scales the triage across all 153 without changing the discovery rule.
