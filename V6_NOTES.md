# V6 — assessment normalization + paid-data firewall

Implemented:
- Annual assessment-history importer keyed by parcel + roll year.
- Assessment value, official market-value field and later AVM estimates remain separate.
- ATTOM trial adapter boundary is ready but dormant until credentials are supplied.
- ATTOM is treated as optional enrichment, not the system of record.

Decision rule before paying:
A paid field must be (1) unavailable/poor in official data, (2) useful to WHY NOW / qualification / market context,
and (3) measurable against actual seller outcomes.

Current likely paid-data value:
- normalized deeper sales/loan/assessment history
- possible building permit/home-equity enrichment
- faster normalized access across expansion geographies

Current NOT solved by ordinary Property API alone:
- full live MLS/listing-history access without the relevant MLS/licensing path.

Subscription strategy:
Run official-data engine first. Use ATTOM trial against the same pilot parcels. Measure incremental fields and
incremental actionable signals. Pay only if it materially improves the opportunity pipeline or labor cost.
