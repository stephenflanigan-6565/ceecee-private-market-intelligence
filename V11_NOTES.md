# V11 — Insert-ID Portability Repair / Pre-Deployment Gate

- Added portable `insert_id()` helper: SQLite uses `lastrowid`; PostgreSQL uses `RETURNING`.
- Repaired runtime job insert-ID handling.
- Repaired eligible collector/transfer insert-ID handling.
- Re-runs portability and local integration checks.
- Outreach remains OFF.

This closes the known static SQLite/PostgreSQL insert-ID mismatch. The next meaningful proof requires a real PostgreSQL runtime and internet-connected source execution; local SQLite testing cannot substitute for that.
