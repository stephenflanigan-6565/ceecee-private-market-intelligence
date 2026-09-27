# V9 — Database / Container Deployment Foundation

V9 converts the runtime target from a local-only concept into a portable deployment package.

Added:
- `db.py`: SQLite/PostgreSQL connection abstraction.
- `schema_postgres.sql`: PostgreSQL-native runtime/operator tables.
- `requirements.txt`: psycopg deployment dependency.
- `Dockerfile`: portable service container.
- `docker-compose.local.yml`: local PostgreSQL integration environment.
- `jobs.json`: explicit daily/weekly/monthly/publication/on-demand job plan.
- `deploy_check.py`: refuses a research deployment unless dry-run is ON, outreach is OFF, database is configured, and official adapters are enabled.

Important boundary:
The historical V1–V7 collectors are preserved. They still require incremental conversion to use `db.py` before every collector is PostgreSQL-native. V9 does not falsely claim that conversion is complete.

Deployment sequence:
1. Create hosted PostgreSQL/runtime.
2. Load `schema_postgres.sql`.
3. Set DATABASE_URL.
4. Run `deploy_check.py`.
5. Convert/run official collectors through portable DB layer.
6. First Westhampton live research collection.
7. Keep outreach OFF until separate compliance/authorization gate.
