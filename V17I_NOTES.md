V17I tests append-only/idempotent persistence only.
It does NOT invent or ingest real Clerk evidence.
The test row is permanently marked controlled_test=1 and cannot be confused with operational verified evidence.
Run endpoint twice to prove first-run insert and second-run idempotency.
