# V15K7 — Raw Suffolk SBL Parser Repair

## LOCK → CHANGE → VERIFY → STOP

**Protected baseline:** V15K5 normalization / V15K6 residual diagnostic.

**Observed failure:** 75 NYS records were classified as unparsable because their SBL values are 20-digit fixed-width Suffolk keys rather than hyphenated print keys. V15K6 exposed the raw values and made the encoding deterministic.

**Allowed change:** Extend `key_from_sbl()` only to decode the 20-digit form:

- `01000000060190000000` → `10-6-19`
- `01100000010100010000` → `11-1-10.001`
- `00300100010050000000` → `3.001-1-5`
- `01300000020180030000` → `13-2-18.003`

The existing human-readable SBL parser and canonical normalization are unchanged.

## Safety

- READ ONLY
- zero database writes
- no assessment persistence
- no seller scoring
- no signals/events/opportunities
- no outreach
- V15J remains untouched

## Verification target

Run the existing endpoint `/api/westhampton-universe/assessment-probe-v15k`. Compare against V15K6 baseline: 2,416 matched canonical parcels (94.93%), 75 unparsable state records, 9 parsed-but-unmatched state keys.
