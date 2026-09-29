# V16K1 — Operations Console Startup Repair

Isolated repair only.

Failure observed in DigitalOcean deploy logs: `operations_console_v16k.py` imported private names `_connect` and `_placeholder` from `evidence_memory`, but the protected database contract exposes `connect`/`execute` through `db`.

Repair:
- use the proven `db.connect` / `db.execute` contract;
- query the actual locked tables: `evidence_ledger`, `evidence_change_events`, `investigation_state`;
- preserve V16K routes, read-only guards, V16J1 inbox, and all V16A–V16I logic unchanged.

Verification target: Gunicorn boots, `/api/intelligence/operations-console-v16k` returns status ok, then `/operations` renders.
