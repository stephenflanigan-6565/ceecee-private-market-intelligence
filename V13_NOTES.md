# V13 Cloud Runtime Repair

Purpose: repair the DigitalOcean deployment boundary exposed by the first live cloud run.

Confirmed observation from V12:
- Container started successfully.
- operator_report.py completed successfully.
- Exit code was 0.
- DigitalOcean marked the component failed because a Web Service must remain alive.

Allowed change:
- Preserve V12 intelligence/data modules.
- Replace Docker startup command with persistent Gunicorn web process.
- Add minimal Flask operator/health surface.
- Make operator_report portable across SQLite/PostgreSQL.
- Expand PostgreSQL schema to the full V12 table model.
- Keep CEECEE_DRY_RUN=1 and CEECEE_OUTREACH_ENABLED=0.

Routes:
- / : operator status page
- /health : platform health endpoint
- /api/status : read-only JSON status

Next external proof:
1. Deploy as DigitalOcean Web Service.
2. Confirm /health returns 200.
3. Attach PostgreSQL and set DATABASE_URL.
4. Run bootstrap_db.py.
5. Confirm /api/status reports database_backend=postgres.
6. Only then activate official collection jobs.
