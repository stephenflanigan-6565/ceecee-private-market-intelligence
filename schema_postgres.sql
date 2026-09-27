
CREATE TABLE IF NOT EXISTS runtime_runs(
 id BIGSERIAL PRIMARY KEY,
 run_key TEXT NOT NULL,
 job_name TEXT NOT NULL,
 started_at TIMESTAMPTZ NOT NULL,
 finished_at TIMESTAMPTZ,
 status TEXT NOT NULL,
 attempt INTEGER NOT NULL DEFAULT 1,
 records_seen INTEGER NOT NULL DEFAULT 0,
 records_changed INTEGER NOT NULL DEFAULT 0,
 error_text TEXT
);
CREATE TABLE IF NOT EXISTS adapter_registry(
 adapter_key TEXT PRIMARY KEY,
 category TEXT NOT NULL,
 enabled BOOLEAN NOT NULL DEFAULT FALSE,
 credential_required BOOLEAN NOT NULL DEFAULT FALSE,
 paid BOOLEAN NOT NULL DEFAULT FALSE,
 status TEXT NOT NULL DEFAULT 'AVAILABLE',
 last_checked_at TIMESTAMPTZ,
 notes TEXT
);
CREATE TABLE IF NOT EXISTS source_schedule(
 source_key TEXT PRIMARY KEY,
 cadence TEXT NOT NULL,
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 last_success_at TIMESTAMPTZ,
 next_due_at TIMESTAMPTZ,
 priority INTEGER NOT NULL DEFAULT 100,
 notes TEXT
);
CREATE TABLE IF NOT EXISTS contact_governor(
 parcel_id TEXT PRIMARY KEY,
 opportunity_state TEXT NOT NULL,
 why_now TEXT,
 evidence_summary JSONB,
 compliance_state TEXT NOT NULL DEFAULT 'NOT_CHECKED',
 outreach_authorized BOOLEAN NOT NULL DEFAULT FALSE,
 governor_decision TEXT NOT NULL DEFAULT 'NO_CONTACT',
 updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS buyer_requirements(
 id BIGSERIAL PRIMARY KEY,
 buyer_key TEXT NOT NULL,
 geography TEXT,
 budget_min NUMERIC,
 budget_max NUMERIC,
 waterfront TEXT,
 acreage_min NUMERIC,
 architecture TEXT,
 beds_min INTEGER,
 pool_required BOOLEAN,
 dock_required BOOLEAN,
 privacy_notes TEXT,
 renovation_tolerance TEXT,
 timing TEXT,
 off_market_preference TEXT,
 qualification_state TEXT,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 observed_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS legacy_relationships(
 id BIGSERIAL PRIMARY KEY,
 person_key TEXT,
 parcel_id TEXT,
 source_system TEXT NOT NULL,
 source_record_id TEXT,
 relationship_date DATE,
 relationship_type TEXT,
 notes TEXT,
 confidence TEXT DEFAULT 'UNVERIFIED',
 imported_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_snapshots(
 id BIGSERIAL PRIMARY KEY,
 generated_at TIMESTAMPTZ NOT NULL,
 ignore_count INTEGER NOT NULL DEFAULT 0,
 watch_count INTEGER NOT NULL DEFAULT 0,
 investigate_count INTEGER NOT NULL DEFAULT 0,
 latent_count INTEGER NOT NULL DEFAULT 0,
 active_count INTEGER NOT NULL DEFAULT 0,
 contact_eligible_count INTEGER NOT NULL DEFAULT 0,
 failures_24h INTEGER NOT NULL DEFAULT 0,
 payload JSONB
);
