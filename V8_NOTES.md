# V8 — Deployment / Operator Foundation

V8 adds the runtime layer needed before live deployment.

## Added
- Environment-based runtime configuration.
- Adapter registry with free/official, proprietary, commercial, and licensed data rails.
- Paid adapters stay dormant until credentials are supplied.
- Runtime job ledger with retries and failure capture.
- Operator snapshot/report: IGNORE, WATCH, INVESTIGATE, LATENT, ACTIVE, contact-eligible, failures, adapter status.
- Deployment environment template.
- Outreach remains hard-OFF by default.

## Safety / operating boundary
`CEECEE_OUTREACH_ENABLED=0` by default.
The runtime wrapper exposes research/maintenance/report jobs only.
No property signal or INVESTIGATE state can independently authorize homeowner contact.

## PostgreSQL
The deployment environment now carries DATABASE_URL so the hosted target is explicit.
Existing V1–V7 SQLite modules are preserved rather than silently rewritten. A database abstraction/migration pass is still required before those modules can run directly against PostgreSQL.

## Next execution boundary
1. Add a database-access abstraction and PostgreSQL-compatible schema/migrations.
2. Package the service/container and scheduled-job definitions.
3. Deploy to the chosen internet-connected runtime.
4. Execute the first real Westhampton collection.
