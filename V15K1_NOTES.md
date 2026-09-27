# V15K1 — Assessment Roll Download Transport Repair

## Problem isolated
V15K reached the read-only assessment probe but DigitalOcean timed out while downloading the official Southampton PDF. No database writes occurred.

## Allowed change
Transport only. The canonical join logic, tax-map normalization, database query, and zero-write safety rails are unchanged.

## Repair
- Preserve the original official Southampton Town DocumentCenter URL as the primary source.
- Add the official Southampton Town Police DocumentCenter host as a fallback for the same document ID/path.
- Use bounded 45-second attempts with browser-compatible request headers and Connection: close.
- Report the official host that actually served the PDF.

## Verification target
Existing route remains exactly:
`/api/westhampton-universe/assessment-probe-v15k`

Expected safety flags remain:
- database_writes = 0
- assessment_data_touched = false
- seller_scoring_touched = false
- opportunity_data_touched = false
- outreach_touched = false

V15J remains protected and unchanged.
