# V5 — parcel lineage + physical-property context + assessment staging

Added:
- Historic parcel lineage table/adapter using Suffolk's official Historic Parcel service.
- Building footprint context using Southampton ePortal's queryable footprint layer.
- Assessment-history schema ready for normalized annual Westhampton Beach roll imports.
- Existing current parcel, owner, transfer, transfer-party and zoning rails remain intact.

Effect:
The machine can preserve a parcel's prior states instead of losing context when a parcel is retired/changed, and can retain physical building context separately from seller signals.

Important:
Assessment PDF normalization is staged but not falsely represented as fully automated yet.
Listing/market history remains the principal paid-data gap.
