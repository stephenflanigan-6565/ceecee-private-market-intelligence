"""Append-only review memory, separate from the legacy evidence ledger.

SQLite is an explicit local development store. The PostgreSQL adapter uses the
same schema but requires an operator-applied migration; it never creates tables.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import sqlite3

SCHEMA = """CREATE TABLE IF NOT EXISTS pmi_ai_review_records (
 record_key TEXT PRIMARY KEY, kind TEXT NOT NULL,
 case_id TEXT NOT NULL, analysis_id TEXT NOT NULL,
 data_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS pmi_ai_review_case
 ON pmi_ai_review_records(case_id, kind);"""

OUTCOMES = {
    "USEFUL_INVESTIGATION", "FALSE_POSITIVE", "SELLER_REASON_CONFIRMED",
    "SELLER_REASON_DISPROVED", "NO_SELLER_REASON_FOUND", "SOURCE_ERROR",
}
METHODS = {"OPERATOR_REVIEW", "OWNER_DISCLOSURE", "AUTHORITATIVE_RECORD"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReviewMemory:
    def __init__(self, path):
        self.factory = lambda: sqlite3.connect(path)
        self.postgres = False
        with self._session() as connection:
            connection.executescript(SCHEMA)

    @classmethod
    def postgres_store(cls, dsn):
        import psycopg
        store = cls.__new__(cls)
        store.factory = lambda: psycopg.connect(dsn)
        store.postgres = True
        # Readiness check only. Apply the supplied migration separately.
        with store._session() as connection:
            connection.execute("SELECT record_key FROM pmi_ai_review_records LIMIT 1")
        return store

    @contextmanager
    def _session(self):
        connection = self.factory()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _execute(self, connection, sql, params=()):
        return connection.execute(sql.replace("?", "%s") if self.postgres else sql, params)

    def _get(self, key):
        with self._session() as connection:
            row = self._execute(connection,
                "SELECT data_json FROM pmi_ai_review_records WHERE record_key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _append(self, key, kind, case_id, analysis_id, payload):
        serialized = canonical(payload)
        with self._session() as connection:
            self._execute(connection, """INSERT INTO pmi_ai_review_records
                (record_key,kind,case_id,analysis_id,data_json,recorded_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(record_key) DO NOTHING""",
                (key, kind, case_id, analysis_id, serialized,
                 datetime.now(timezone.utc).isoformat()))
            stored = self._execute(connection,
                "SELECT data_json FROM pmi_ai_review_records WHERE record_key=?", (key,)).fetchone()
            if stored[0] != serialized:
                raise ValueError("An existing record cannot be overwritten; use a new review event.")
        return json.loads(stored[0])

    def remember_analysis(self, analysis):
        content = {key: value for key, value in analysis.items() if key != "analysis_id"}
        if analysis.get("analysis_id") != digest(content):
            raise ValueError("Analysis identifier does not match its content.")
        return self._append("analysis:" + analysis["analysis_id"], "ANALYSIS",
                            analysis["case_id"], analysis["analysis_id"], analysis)

    def analysis(self, analysis_id):
        return self._get("analysis:" + analysis_id)

    def review(self, *, event_id, analysis_id, hypothesis_id, actor, outcome,
               method, detail, verified=False, supersedes=None):
        for value in (event_id, hypothesis_id, actor, detail):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Review identity, actor, hypothesis, and finding are required.")
        if len(event_id) > 128 or len(detail) > 8000:
            raise ValueError("Review identifiers or findings exceed the supported size.")
        if outcome not in OUTCOMES or method not in METHODS or type(verified) is not bool:
            raise ValueError("Unsupported review outcome or evidence method.")
        if outcome == "SELLER_REASON_CONFIRMED" and method != "OWNER_DISCLOSURE":
            raise ValueError("Seller confirmation requires the owner's disclosed reason.")
        analysis = self.analysis(analysis_id)
        if analysis is None:
            raise ValueError("Review must reference a stored analysis.")
        hypothesis = next((item for item in analysis["hypotheses"]
                           if item["hypothesis_id"] == hypothesis_id), None)
        if hypothesis is None:
            raise ValueError("Unknown hypothesis in the referenced analysis.")
        if supersedes is not None:
            previous = self._get("feedback:" + supersedes)
            if previous is None or (previous["analysis_id"], previous["hypothesis_id"]) != (
                    analysis_id, hypothesis_id):
                raise ValueError("Correction must reference the same analysis and hypothesis.")
        payload = {
            "event_id": event_id, "analysis_id": analysis_id,
            "case_id": analysis["case_id"], "case_revision": analysis["case_revision"],
            "hypothesis_id": hypothesis_id, "actor": actor, "outcome": outcome,
            "method": method, "detail": detail, "verified": verified,
            "supersedes": supersedes,
            "pattern_tags": hypothesis["pattern_tags"],
        }
        return self._append("feedback:" + event_id, "FEEDBACK",
                            payload["case_id"], analysis_id, payload)

    def history(self, case_id):
        with self._session() as connection:
            rows = self._execute(connection, """SELECT kind,data_json,recorded_at
                FROM pmi_ai_review_records WHERE case_id=?
                ORDER BY recorded_at,record_key""", (case_id,)).fetchall()
        return [{"kind": row[0], "data": json.loads(row[1]), "recorded_at": row[2]}
                for row in rows]

    def lessons(self):
        """Empirical feedback counts, never a seller score or automatic rule.

        Each property contributes its latest verified outcome to a pattern.
        Replaying an analysis or review cannot inflate the counts.
        Reviewer prose and personal details stay out of the model context.
        """
        with self._session() as connection:
            rows = self._execute(connection, """SELECT data_json FROM pmi_ai_review_records
                WHERE kind='FEEDBACK' ORDER BY recorded_at,record_key""").fetchall()
        latest = {}
        for row in rows:
            event = json.loads(row[0])
            if event["verified"]:
                for tag in event["pattern_tags"]:
                    latest[(event["case_id"], tag)] = event["outcome"]
        patterns = {}
        for (_, tag), outcome in latest.items():
            counts = patterns.setdefault(tag, {})
            counts[outcome] = counts.get(outcome, 0) + 1
        return [{"pattern": tag, "reviewed_properties": sum(counts.values()),
                 "outcomes": dict(sorted(counts.items()))}
                for tag, counts in sorted(patterns.items())]
