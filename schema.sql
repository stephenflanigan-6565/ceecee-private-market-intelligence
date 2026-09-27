
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS properties(
 parcel_id TEXT PRIMARY KEY, district TEXT, section TEXT, block TEXT, lot TEXT,
 municipality TEXT, zipcode TEXT, full_address TEXT, acreage REAL, frontage TEXT,
 depth TEXT, land_use TEXT, title_flag TEXT, status TEXT, deed_acreage REAL,
 source_created_at TEXT, source_last_update TEXT, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS owners(
 id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id TEXT NOT NULL, owner_name TEXT,
 first_name TEXT, last_name TEXT, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, UNIQUE(parcel_id,owner_name,first_name,last_name)
);
CREATE TABLE IF NOT EXISTS snapshots(
 id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id TEXT NOT NULL, source TEXT NOT NULL,
 observed_at TEXT NOT NULL, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
 UNIQUE(parcel_id,source,payload_hash)
);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id TEXT NOT NULL, event_type TEXT NOT NULL,
 event_date TEXT, observed_at TEXT NOT NULL, source TEXT NOT NULL,
 evidence_grade TEXT NOT NULL, details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals(
 id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id TEXT NOT NULL, signal_type TEXT NOT NULL,
 observed_at TEXT NOT NULL, source_event_id INTEGER, confidence TEXT NOT NULL DEFAULT 'HIGH',
 active INTEGER NOT NULL DEFAULT 1, UNIQUE(parcel_id,signal_type,source_event_id)
);
CREATE TABLE IF NOT EXISTS opportunities(
 parcel_id TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'IGNORE', why_now TEXT,
 independent_signal_types INTEGER NOT NULL DEFAULT 0, compliance_state TEXT NOT NULL DEFAULT 'PENDING',
 contact_state TEXT NOT NULL DEFAULT 'NEW', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, started_at TEXT NOT NULL,
 completed_at TEXT, records_seen INTEGER DEFAULT 0, changed_records INTEGER DEFAULT 0,
 status TEXT NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS outcomes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id TEXT NOT NULL, campaign_arm TEXT,
 channel TEXT, response_state TEXT, appointment_state TEXT, listing_state TEXT,
 closed_state TEXT, spend REAL, revenue REAL, observed_at TEXT NOT NULL, notes TEXT
);

CREATE TABLE IF NOT EXISTS transfers(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parcel_id TEXT NOT NULL,
 history_sequence REAL,
 liber_page TEXT,
 record_date TEXT,
 document_number TEXT,
 document_code TEXT,
 document_date TEXT,
 entry_date TEXT,
 sale_date TEXT,
 sale_price REAL,
 source TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 UNIQUE(parcel_id,history_sequence,document_number,source)
);
CREATE INDEX IF NOT EXISTS idx_transfers_parcel ON transfers(parcel_id);
CREATE INDEX IF NOT EXISTS idx_events_parcel ON events(parcel_id);
CREATE INDEX IF NOT EXISTS idx_signals_parcel ON signals(parcel_id);

CREATE TABLE IF NOT EXISTS transfer_parties(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parcel_id TEXT NOT NULL,
 history_sequence REAL,
 role TEXT NOT NULL,
 first_name TEXT,
 last_name TEXT,
 middle_initial TEXT,
 suffix TEXT,
 ownership_percent REAL,
 owner_type TEXT,
 business_flag TEXT,
 source TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 UNIQUE(parcel_id,history_sequence,role,first_name,last_name,middle_initial,suffix)
);
CREATE TABLE IF NOT EXISTS property_context(
 parcel_id TEXT PRIMARY KEY,
 zoning_code TEXT,
 zoning_name TEXT,
 zoning_description TEXT,
 zoning_dimensional_regulation TEXT,
 building_footprint_present INTEGER,
 context_observed_at TEXT NOT NULL,
 context_source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parcel_lineage(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parcel_id TEXT NOT NULL,
 status TEXT,
 full_address TEXT,
 acreage REAL,
 frontage TEXT,
 depth TEXT,
 land_use TEXT,
 source_created_at TEXT,
 source_last_update TEXT,
 observed_at TEXT NOT NULL,
 source TEXT NOT NULL,
 UNIQUE(parcel_id,status,source_last_update,source)
);
CREATE TABLE IF NOT EXISTS assessment_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parcel_id TEXT NOT NULL,
 roll_year INTEGER NOT NULL,
 assessed_land REAL,
 assessed_total REAL,
 market_value REAL,
 acreage REAL,
 property_class TEXT,
 source TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 UNIQUE(parcel_id,roll_year,source)
);
CREATE TABLE IF NOT EXISTS building_context(
 parcel_id TEXT PRIMARY KEY,
 building_count INTEGER,
 footprint_area REAL,
 footprint_perimeter REAL,
 observed_at TEXT NOT NULL,
 source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_schedule(
 source_key TEXT PRIMARY KEY,
 cadence TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1,
 last_success_at TEXT,
 next_due_at TEXT,
 priority INTEGER NOT NULL DEFAULT 100,
 notes TEXT
);
CREATE TABLE IF NOT EXISTS contact_governor(
 parcel_id TEXT PRIMARY KEY,
 opportunity_state TEXT NOT NULL,
 why_now TEXT,
 evidence_summary TEXT,
 compliance_state TEXT NOT NULL DEFAULT 'NOT_CHECKED',
 outreach_authorized INTEGER NOT NULL DEFAULT 0,
 governor_decision TEXT NOT NULL DEFAULT 'NO_CONTACT',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS buyer_requirements(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 buyer_key TEXT NOT NULL,
 geography TEXT,
 budget_min REAL,
 budget_max REAL,
 waterfront TEXT,
 acreage_min REAL,
 architecture TEXT,
 beds_min INTEGER,
 pool_required INTEGER,
 dock_required INTEGER,
 privacy_notes TEXT,
 renovation_tolerance TEXT,
 timing TEXT,
 off_market_preference TEXT,
 qualification_state TEXT,
 active INTEGER NOT NULL DEFAULT 1,
 observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legacy_relationships(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 person_key TEXT,
 parcel_id TEXT,
 source_system TEXT NOT NULL,
 source_record_id TEXT,
 relationship_date TEXT,
 relationship_type TEXT,
 notes TEXT,
 confidence TEXT DEFAULT 'UNVERIFIED',
 imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_key TEXT NOT NULL,
 job_name TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT,
 status TEXT NOT NULL,
 attempt INTEGER NOT NULL DEFAULT 1,
 records_seen INTEGER NOT NULL DEFAULT 0,
 records_changed INTEGER NOT NULL DEFAULT 0,
 error_text TEXT
);
CREATE TABLE IF NOT EXISTS adapter_registry(
 adapter_key TEXT PRIMARY KEY,
 category TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 0,
 credential_required INTEGER NOT NULL DEFAULT 0,
 paid INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'AVAILABLE',
 last_checked_at TEXT,
 notes TEXT
);
CREATE TABLE IF NOT EXISTS operator_snapshots(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 generated_at TEXT NOT NULL,
 ignore_count INTEGER NOT NULL DEFAULT 0,
 watch_count INTEGER NOT NULL DEFAULT 0,
 investigate_count INTEGER NOT NULL DEFAULT 0,
 latent_count INTEGER NOT NULL DEFAULT 0,
 active_count INTEGER NOT NULL DEFAULT 0,
 contact_eligible_count INTEGER NOT NULL DEFAULT 0,
 failures_24h INTEGER NOT NULL DEFAULT 0,
 payload TEXT
);

CREATE TABLE IF NOT EXISTS ownership_evidence(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parcel_id TEXT NOT NULL,
 source TEXT NOT NULL,
 source_object_id TEXT NOT NULL,
 owner_name TEXT,
 first_name TEXT,
 last_name TEXT,
 evidence_grade TEXT NOT NULL,
 verification_state TEXT NOT NULL,
 first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL,
 UNIQUE(source,source_object_id)
);
CREATE INDEX IF NOT EXISTS idx_ownership_evidence_parcel ON ownership_evidence(parcel_id);

CREATE TABLE IF NOT EXISTS assessment_evidence(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parcel_id TEXT NOT NULL,
 source TEXT NOT NULL,
 source_object_id TEXT,
 roll_year INTEGER NOT NULL,
 swis TEXT NOT NULL,
 normalized_taxmap TEXT NOT NULL,
 property_class TEXT,
 acreage REAL,
 assessed_land REAL,
 assessed_total REAL,
 full_market_value REAL,
 year_built INTEGER,
 living_sqft REAL,
 bedrooms REAL,
 full_baths REAL,
 parcel_address TEXT,
 building_style TEXT,
 used_as TEXT,
 evidence_grade TEXT NOT NULL DEFAULT 'A',
 first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL,
 UNIQUE(parcel_id,source,roll_year)
);
CREATE INDEX IF NOT EXISTS idx_assessment_evidence_parcel ON assessment_evidence(parcel_id);
