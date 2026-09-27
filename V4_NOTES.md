# V4 — ownership-chain + location intelligence

Added:
- Grantor/grantee party history keyed by parcel + transfer history sequence.
- Ownership percentage/type/business flag when supplied by Suffolk.
- Westhampton Beach zoning/context enrichment using a spatial join.
- Property-context table separated from seller-intent signals.

Why:
This lets the engine reconstruct factual ownership transitions and understand the property's legal/location context without treating either as motivation.

Still deliberately excluded:
- sensitive-life-event profiling
- inferred current mortgage balance
- inferred seller probability
- automatic contact

Remaining major data gap before outreach:
reliable listing/market-history feed and assessment normalization, followed by CeeCee legacy import.
