# V15J — Ownership + Transfer Evidence Persistence

Purpose: persist the two official Suffolk evidence layers already validated by V15I across the locked Westhampton Beach district 0905 universe.

## Locked inputs
- 2,545 canonical active parcels.
- V15I measured TaxParcelOwner coverage at 100% (2,545/2,545).
- V15I measured TaxParcelTransferHistory coverage at 99.14% overall and 99.95% across the residential-side cohort.

## Allowed change
- Add a separate `ownership_evidence` table with official-source provenance and source OBJECTID.
- Persist current TaxParcelOwner source records as evidence grade A with default verification state `PROBABLE`.
- Persist TaxParcelTransferHistory factual document history into the existing `transfers` evidence table.
- Normalize ArcGIS date values to UTC ISO text.
- Preserve idempotency: reruns update/verify existing evidence rather than duplicating it.

## Explicitly protected
- No seller scoring.
- No opportunities or WHY NOW conclusions.
- No events or signals are created from transfer records in this step.
- No outreach authorization or homeowner contact.
- Existing property and classification layers are not modified.

## Ownership Verification Gate
`PROBABLE` is intentional. A single official current-owner source is strong factual evidence but is not automatically promoted to `VERIFIED` for owner-addressed outreach. Later corroboration (assessment/Clerk/other authoritative evidence) can promote the status. Questionable ownership remains subject to manual verification before contact.

## Verification target
Expected first live run should persist approximately 4,876 owner-source records and 14,590 transfer-history records, covering the counts measured in V15I. Exact counts are verified from the live response rather than assumed.
