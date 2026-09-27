# V10 — Portable DB Conversion Pass

Purpose: move the executable operating modules onto the V9 database abstraction instead of leaving them tied directly to SQLite.

Completed:
- Replaced direct `sqlite3.connect(DB)` calls in eligible operating modules with `db.connect()`.
- Added backend-selecting database bootstrapper.
- Added portability audit for remaining hard-coded SQLite connections and known dialect traps.
- Added deterministic deployment manifest.
- Preserved all source adapters and outreach lock.

Important qualification:
This pass makes connection handling portable, but PostgreSQL execution still must be integration-tested against a real PostgreSQL instance. SQLite smoke tests cannot prove PostgreSQL behavior. Any module using SQLite-specific exception classes or row/insert semantics must be validated during hosted integration.

Next:
- run full integration against PostgreSQL;
- repair any dialect-specific behavior found;
- wire actual scheduled collector commands;
- first live Westhampton research collection.
