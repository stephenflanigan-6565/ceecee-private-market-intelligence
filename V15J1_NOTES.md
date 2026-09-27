# V15J1 — PostgreSQL Nullable-Key Parameter Type Repair

## Scope
Surgical repair only. No schema changes and no architecture changes.

## Root cause
V15J's transfer-history existence lookup used duplicate nullable placeholders in `? IS NULL` expressions. After portable placeholder conversion, PostgreSQL could not infer the datatype of the nullable parameter and raised `IndeterminateDatatype` (`could not determine data type of parameter $6`).

## Repair
For PostgreSQL only, the transfer-history lookup now uses `IS NOT DISTINCT FROM` with explicit casts matching the proven schema:
- `history_sequence` -> `DOUBLE PRECISION`
- `document_number` -> `TEXT`

SQLite retains the prior portable nullable comparison.

## Protected systems
- No database schema modification.
- Canonical properties untouched.
- Factual classifications untouched.
- No seller scoring.
- No opportunity generation.
- No outreach.
- Existing V15J transaction rollback remains intact on any exception.

## Verification target
Run the existing `/api/westhampton-universe/evidence-persist-v15j` endpoint. Expected source counts remain approximately 4,876 ownership records and 14,590 transfer-history records based on V15I. Then rerun once to verify idempotency.
