# CEECEE V14 — Cloud Memory Persistence Verification

Purpose: prove PostgreSQL persistence across a DigitalOcean redeploy without inserting fake homeowner, property, opportunity, campaign, or outreach data.

Changes only:
- Adds `cloud_memory_check.py` with a dedicated `cloud_runtime_checks` infrastructure table.
- Adds read/test route `/api/cloud-memory-check`.
- First call creates one constant marker; later calls update only its last-seen time and count.
- Response exposes only infrastructure verification fields.
- Does not touch property/owner/opportunity tables.
- Does not enable or invoke outreach.

Verification sequence:
1. Deploy V14 while `DATABASE_URL` is bound to PostgreSQL.
2. Open `/api/cloud-memory-check`; record `first_seen_utc` and `check_count`.
3. Redeploy the same V14 commit/image.
4. Open `/api/cloud-memory-check` again.
5. PASS if `database_backend` remains `postgres`, `first_seen_utc` is unchanged, and `check_count` increases.

Rollback: V13 Cloud Runtime Repair.
