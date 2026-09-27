# V15I — Ownership + Transfer History Coverage Measurement

Purpose: measure Suffolk TaxParcelOwner and TaxParcelTransferHistory coverage across the locked Westhampton Beach canonical universe before permanent ingestion.

Controls:
- Read only; zero database writes.
- Requests PARCELID only from Owner; no owner names.
- Transfer History requests PARCELID + TRANSHISSEQ only; no party names.
- Uses proven canonical filter: district 0905 + status A.
- Joins persisted V15E factual cohorts only for residential-side coverage measurement.
- No seller scoring, opportunity generation, Contact Governor changes, or outreach.
- Paged upstream reads with a 50-page safety ceiling.

Endpoint: /api/westhampton-universe/coverage-v15i

Pass gate: coherent canonical/residential totals and successful owner/history coverage metrics. Permanent ingestion remains a later, separately authorized step.
