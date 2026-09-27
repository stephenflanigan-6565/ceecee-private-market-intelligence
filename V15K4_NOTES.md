# V15K4 — Canonical Block Scale Repair

## Failure isolated
V15K3 proved the section and lot normalization but exposed a single block-scale defect.

Live evidence:
- Canonical emitted `1-0.1-1.001` while NYS emitted `1-1-1.001`.
- Canonical emitted `10-0.1-10` while NYS emitted `10-1-10`.

The block component was divided by 1000; the observed canonical storage requires division by 100.

## Allowed change
Only `canonical_key()` block scaling changes: `1000 -> 100`.

No database schema, persistence, ownership, transfer history, scoring, signals, opportunities, or outreach changes. Probe remains read-only with zero database writes.

## Verification target
Existing route: `/api/westhampton-universe/assessment-probe-v15k`
Expected: canonical keys align with NYS examples and matched parcel coverage rises materially above zero.
