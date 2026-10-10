-- Apply only when activating the separately reviewed seller AI memory.
-- No existing evidence, watch, opportunity, or V19V table is altered.
CREATE TABLE IF NOT EXISTS pmi_ai_review_records (
    record_key TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    case_id TEXT NOT NULL,
    analysis_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pmi_ai_review_case
    ON pmi_ai_review_records(case_id, kind);
