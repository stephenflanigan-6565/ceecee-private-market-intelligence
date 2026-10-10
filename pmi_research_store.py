"""Durable, case-scoped research scheduling and source observation history.

Reads never migrate or fetch. Research writes share the operator workspace's
transaction lock but do not replace its cases, evidence, feedback or analysis.
"""
import copy
from datetime import datetime, timedelta, timezone
import json
import re
import uuid

from pmi_review_store import ReviewStore, _bool, _text
from seller_ai_memory import canonical, digest

LEASE_SECONDS = 180
SUCCESS_SECONDS = 24 * 60 * 60
RETRY_SECONDS = 6 * 60 * 60
COOLDOWN_SECONDS = 5 * 60
SOURCE_KEYS = {"parcel", "owner", "transfer_current", "transfer_history"}
RUN_STATUSES = {"SUCCESS", "PARTIAL", "ERROR", "UNSUPPORTED"}
SOURCE_STATUSES = {"SUCCESS", "EMPTY", "ERROR", "INCOMPLETE", "UNSUPPORTED"}
TABLES = ("pmi_research_control", "pmi_research_schedule", "pmi_research_runs",
          "pmi_research_snapshots", "pmi_research_sources")
SCHEMA = """
CREATE TABLE IF NOT EXISTS pmi_research_control (
 control_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL,
 lease_run_id TEXT, lease_token TEXT, lease_until TEXT,
 actor TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pmi_research_schedule (
 case_id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL,
 next_due_at TEXT NOT NULL, requested INTEGER NOT NULL,
 last_attempt_at TEXT, last_completed_at TEXT);
CREATE TABLE IF NOT EXISTS pmi_research_runs (
 run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, parcel_id TEXT NOT NULL,
 case_json TEXT NOT NULL, worker_id TEXT NOT NULL, lease_token TEXT NOT NULL,
 started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL,
 bundle_json TEXT);
CREATE INDEX IF NOT EXISTS pmi_research_runs_case ON pmi_research_runs(case_id, started_at);
CREATE TABLE IF NOT EXISTS pmi_research_snapshots (
 snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, parcel_id TEXT NOT NULL,
 source_key TEXT NOT NULL, content_hash TEXT NOT NULL,
 source_json TEXT NOT NULL, first_checked_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pmi_research_sources (
 case_id TEXT NOT NULL, source_key TEXT NOT NULL, snapshot_id TEXT NOT NULL,
 checked_at TEXT NOT NULL, source_json TEXT NOT NULL,
 PRIMARY KEY(case_id, source_key));
"""


def _moment(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Research timestamps require a UTC-aware instant.")
    return value.astimezone(timezone.utc)


def _stamp(value=None):
    return _moment(value).isoformat()


class ResearchStore(ReviewStore):
    def _connect(self, *, write=False):
        if self.postgres:
            import psycopg
            # A storage outage must not strand a daemon's connection attempt.
            return psycopg.connect(self.dsn, connect_timeout=5)
        return super()._connect(write=write)

    def review_ready(self):
        return super().ready()

    def ready(self):
        try:
            with self._session() as connection:
                for table in TABLES:
                    self._sql(connection, "SELECT 1 FROM " + table + " LIMIT 1")
                row = self._sql(connection, "SELECT 1 FROM pmi_research_control WHERE control_id=1").fetchone()
            return bool(row)
        except Exception:
            return False

    def initialize(self):
        if not self.review_ready():
            raise ValueError("Prepare the protected review workspace before research can start.")
        with self._session(write=True) as connection:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    self._sql(connection, statement)
            self._sql(connection, "INSERT INTO pmi_research_control(control_id,enabled,actor,updated_at) VALUES(1,1,?,?) ON CONFLICT(control_id) DO NOTHING", ("CC startup", _stamp()))
        return {"status": "ok", "ready": True}

    def _require_research(self):
        if not self.ready() or not self.review_ready():
            raise ValueError("CC research is waiting for workspace startup.")

    def _pilots(self, connection):
        # Defensive limit preserves the deliberately small sequential pilot.
        rows = self._sql(connection, "SELECT v.data_json,c.state,c.pilot,c.import_id,c.updated_at FROM pmi_review_cases c JOIN pmi_review_case_versions v ON v.version_id=c.version_id WHERE c.pilot=1 AND c.state<>? ORDER BY c.case_id LIMIT 5", ("DISMISSED",)).fetchall()
        return [self._summary(json.loads(row[0]), {"state": row[1], "pilot": True,
                 "import_id": row[3], "updated_at": row[4]}) for row in rows]

    def _schedule(self, connection, case, now):
        self._sql(connection, "INSERT INTO pmi_research_schedule(case_id,parcel_id,next_due_at,requested) VALUES(?,?,?,0) ON CONFLICT(case_id) DO NOTHING", (case["case_id"], case["parcel_id"], _stamp(now)))
        row = self._sql(connection, "SELECT parcel_id,next_due_at,requested,last_attempt_at,last_completed_at FROM pmi_research_schedule WHERE case_id=?", (case["case_id"],)).fetchone()
        if row[0] != case["parcel_id"]:
            raise ValueError("Saved research must remain linked to the same parcel.")
        return row

    def _retained(self, connection, case_id):
        rows = self._sql(connection, "SELECT source_key,source_json,checked_at,snapshot_id FROM pmi_research_sources WHERE case_id=? ORDER BY source_key", (case_id,)).fetchall()
        output = []
        for key, document, checked_at, snapshot_id in rows:
            source = json.loads(document)
            source.update({"source_key": key, "last_successful_check_at": checked_at,
                           "snapshot_id": snapshot_id})
            output.append(source)
        return output

    def _run(self, row):
        run_id, case_id, parcel_id, case_json, started_at, completed_at, status, bundle_json = row
        case = json.loads(case_json)
        return {"run_id": run_id, "case_id": case_id, "parcel_id": parcel_id,
                "property_address": case.get("property_address"), "started_at": started_at,
                "completed_at": completed_at, "status": status,
                "human_status": {"SUCCESS": "Checked", "PARTIAL": "Some records unavailable",
                                 "ERROR": "Check could not complete", "UNSUPPORTED": "Parcel source unsupported",
                                 "RUNNING": "Checking records", "INTERRUPTED": "Check interrupted; will retry"}.get(status, status),
                "bundle": json.loads(bundle_json) if bundle_json else None}

    def status(self):
        base = {"available": False, "enabled": False, "running": None,
                "pilot_count": 0, "completed_count": 0, "last_completed_at": None,
                "next_due_at": None, "recent_runs": []}
        if not self.ready() or not self.review_ready():
            return base
        with self._session() as connection:
            control = self._sql(connection, "SELECT enabled,lease_run_id,lease_until FROM pmi_research_control WHERE control_id=1").fetchone()
            pilots = self._pilots(connection)
            ids = {case["case_id"] for case in pilots}
            columns = "run_id,case_id,parcel_id,case_json,started_at,completed_at,status,bundle_json"
            rows = self._sql(connection, "SELECT " + columns + " FROM pmi_research_runs ORDER BY started_at DESC,run_id DESC LIMIT 10").fetchall()
            recent = [self._run(row) for row in rows]
            current = None
            if control[1] and control[2] and _moment(control[2]) > _moment():
                row = self._sql(connection, "SELECT " + columns + " FROM pmi_research_runs WHERE run_id=?", (control[1],)).fetchone()
                current = self._run(row) if row else None
            schedules = self._sql(connection, "SELECT case_id,next_due_at,requested,last_completed_at FROM pmi_research_schedule").fetchall()
            schedules = [row for row in schedules if row[0] in ids]
            attempted = {row[0]: row for row in schedules}
            due = [_stamp() if case["case_id"] not in attempted or attempted[case["case_id"]][2] else attempted[case["case_id"]][1] for case in pilots]
            last = self._sql(connection, "SELECT MAX(completed_at) FROM pmi_research_runs WHERE completed_at IS NOT NULL").fetchone()[0]
            return {**base, "available": True, "enabled": bool(control[0]), "running": current,
                    "pilot_count": len(pilots), "completed_count": sum(bool(row[3]) for row in schedules),
                    "last_completed_at": last, "next_due_at": min(due) if due and control[0] else None,
                    "recent_runs": recent}

    def history(self, case_id, limit=5):
        if not self.ready():
            return []
        limit = max(1, min(int(limit), 10))
        with self._session() as connection:
            columns = "run_id,case_id,parcel_id,case_json,started_at,completed_at,status,bundle_json"
            rows = self._sql(connection, "SELECT " + columns + " FROM pmi_research_runs WHERE case_id=? ORDER BY started_at DESC,run_id DESC LIMIT ?", (case_id, limit)).fetchall()
            return [self._run(row) for row in rows]

    def latest(self, case_id):
        if not self.ready():
            return None
        with self._session() as connection:
            columns = "run_id,case_id,parcel_id,case_json,started_at,completed_at,status,bundle_json"
            row = self._sql(connection, "SELECT " + columns + " FROM pmi_research_runs WHERE case_id=? ORDER BY started_at DESC,run_id DESC LIMIT 1", (case_id,)).fetchone()
            if not row:
                return None
            run = self._run(row)
            result = copy.deepcopy(run["bundle"] or {"case_id": case_id, "parcel_id": run["parcel_id"],
                    "status": run["status"], "observed_at": run["started_at"], "sources": [],
                    "findings": [], "next_checks": [], "change_summary": "The record check is in progress." if run["status"] == "RUNNING" else "The record check was interrupted; previous saved records remain available."})
            result.update({"research_run": {key: value for key, value in run.items() if key != "bundle"},
                           "retained_sources": self._retained(connection, case_id)})
            return result

    def export_payload(self):
        """Private backup of saved research, without lease or connection secrets."""
        if not self.ready():
            return {}
        with self._session() as connection:
            control = self._sql(connection, "SELECT enabled FROM pmi_research_control WHERE control_id=1").fetchone()
            columns = "run_id,case_id,parcel_id,case_json,started_at,completed_at,status,bundle_json"
            runs = self._sql(connection, "SELECT " + columns + " FROM pmi_research_runs ORDER BY started_at,run_id").fetchall()
            snapshots = self._sql(connection, "SELECT snapshot_id,case_id,parcel_id,source_key,content_hash,source_json,first_checked_at FROM pmi_research_snapshots ORDER BY first_checked_at,snapshot_id").fetchall()
            pointers = self._sql(connection, "SELECT case_id,source_key,snapshot_id,checked_at,source_json FROM pmi_research_sources ORDER BY case_id,source_key").fetchall()
            schedules = self._sql(connection, "SELECT case_id,parcel_id,next_due_at,requested,last_attempt_at,last_completed_at FROM pmi_research_schedule ORDER BY case_id").fetchall()
            return {"version": "PMI_RESEARCH_EXPORT_V1", "generated_at": _stamp(),
                    "enabled": bool(control[0]), "runs": [self._run(row) for row in runs],
                    "source_snapshots": [{"snapshot_id": row[0], "case_id": row[1],
                        "parcel_id": row[2], "source_key": row[3], "content_hash": row[4],
                        "source": json.loads(row[5]), "first_checked_at": row[6]} for row in snapshots],
                    "source_pointers": [{"case_id": row[0], "source_key": row[1],
                        "snapshot_id": row[2], "checked_at": row[3],
                        "source": json.loads(row[4])} for row in pointers],
                    "schedules": [{"case_id": row[0], "parcel_id": row[1],
                        "next_due_at": row[2], "requested": bool(row[3]),
                        "last_attempt_at": row[4], "last_completed_at": row[5]} for row in schedules]}

    def set_enabled(self, enabled, actor):
        self._require_research()
        enabled = _bool(enabled, "Research enabled")
        actor = _text(actor, "Operator", 128)
        with self._session(write=True) as connection:
            self._sql(connection, "UPDATE pmi_research_control SET enabled=?,actor=?,updated_at=? WHERE control_id=1", (int(enabled), actor, _stamp()))
        return self.status()

    def request_run(self, case_id, actor):
        self._require_research()
        _text(actor, "Operator", 128)
        with self._session(write=True) as connection:
            now = _moment()
            pilots = self._pilots(connection)
            if case_id is not None:
                pilots = [case for case in pilots if case["case_id"] == case_id]
                if not pilots:
                    raise ValueError("Choose a current pilot property that has not been set aside.")
            count, cooling = 0, 0
            for case in pilots:
                schedule = self._schedule(connection, case, now)
                if schedule[3] and now - _moment(schedule[3]) < timedelta(seconds=COOLDOWN_SECONDS):
                    cooling += 1
                    continue
                self._sql(connection, "UPDATE pmi_research_schedule SET requested=1 WHERE case_id=?", (case["case_id"],))
                count += 1
        return {"request_count": count, "cooldown": bool(cooling), "cooldown_count": cooling}

    def claim_next(self, worker_id, now=None):
        self._require_research()
        worker_id = _text(worker_id, "Worker identifier", 128)
        with self._session(write=True) as connection:
            # Capture live time after obtaining serialization, so waiting for
            # another operator write cannot revive or manufacture an old lease.
            now = _moment(now)
            enabled, active, token, expires = self._sql(connection, "SELECT enabled,lease_run_id,lease_token,lease_until FROM pmi_research_control WHERE control_id=1").fetchone()
            if active:
                if expires and _moment(expires) > now:
                    return None
                row = self._sql(connection, "SELECT case_id FROM pmi_research_runs WHERE run_id=? AND status='RUNNING'", (active,)).fetchone()
                self._sql(connection, "UPDATE pmi_research_runs SET status='INTERRUPTED',completed_at=? WHERE run_id=? AND status='RUNNING'", (_stamp(now), active))
                if row:
                    self._sql(connection, "UPDATE pmi_research_schedule SET next_due_at=? WHERE case_id=?", (_stamp(now + timedelta(seconds=RETRY_SECONDS)), row[0]))
                self._sql(connection, "UPDATE pmi_research_control SET lease_run_id=NULL,lease_token=NULL,lease_until=NULL WHERE control_id=1")
            if not enabled:
                return None
            candidates = []
            for case in self._pilots(connection):
                schedule = self._schedule(connection, case, now)
                if schedule[2] or _moment(schedule[1]) <= now:
                    candidates.append((not bool(schedule[2]), schedule[1], case["case_id"], case))
            if not candidates:
                return None
            case = min(candidates, key=lambda item: item[:3])[3]
            run_id, token = "research_" + uuid.uuid4().hex, uuid.uuid4().hex
            self._sql(connection, "INSERT INTO pmi_research_runs(run_id,case_id,parcel_id,case_json,worker_id,lease_token,started_at,status) VALUES(?,?,?,?,?,?,?,'RUNNING')", (run_id, case["case_id"], case["parcel_id"], canonical(case), worker_id, token, _stamp(now)))
            self._sql(connection, "UPDATE pmi_research_control SET lease_run_id=?,lease_token=?,lease_until=? WHERE control_id=1", (run_id, token, _stamp(now + timedelta(seconds=LEASE_SECONDS))))
            self._sql(connection, "UPDATE pmi_research_schedule SET requested=0,last_attempt_at=? WHERE case_id=?", (_stamp(now), case["case_id"]))
            previous = {source["source_key"]: source for source in self._retained(connection, case["case_id"])}
            return {"run_id": run_id, "lease_token": token, "case": case, "previous_sources": previous}

    def _validate_bundle(self, bundle, case_id, parcel_id):
        if not isinstance(bundle, dict) or bundle.get("case_id") != case_id or bundle.get("parcel_id") != parcel_id:
            raise ValueError("Research results must identify the exact leased case and parcel.")
        if bundle.get("status") not in RUN_STATUSES:
            raise ValueError("Unsupported research result status.")
        if not isinstance(bundle.get("observed_at"), str):
            raise ValueError("Research results require an explicit checked timestamp.")
        _moment(bundle["observed_at"])
        sources = bundle.get("sources")
        if not isinstance(sources, list) or len(sources) > 4:
            raise ValueError("Research sources must be the bounded pilot source set.")
        seen = set()
        for source in sources:
            if not isinstance(source, dict) or source.get("source_key") not in SOURCE_KEYS or source["source_key"] in seen or source.get("status") not in SOURCE_STATUSES:
                raise ValueError("Unsupported or repeated research source.")
            seen.add(source["source_key"])
            if not isinstance(source.get("observed_at"), str):
                raise ValueError("Each record source requires an explicit checked timestamp.")
            _moment(source["observed_at"])
            records = source.get("records", [])
            if not isinstance(records, list) or len(records) > 100 or any(not isinstance(record, dict) for record in records):
                raise ValueError("Research record response exceeded the pilot bounds.")
            if records and (not isinstance(parcel_id, str) or not re.fullmatch(r"[0-9]{19}", parcel_id) or any(record.get("PARCELID") != parcel_id for record in records)):
                raise ValueError("Every research record must match the exact leased 19-digit parcel.")
            if source["status"] in {"SUCCESS", "EMPTY"} and source.get("complete") is not True:
                raise ValueError("Successful record checks must be reconciled and complete.")
            if source["status"] in {"SUCCESS", "EMPTY"} and (type(source.get("expected_count")) is not int or source["expected_count"] != len(records)):
                raise ValueError("Successful record checks must reconcile the reported count.")
            if source["status"] == "EMPTY" and records:
                raise ValueError("An empty check cannot contain records.")
        for field in ("findings", "next_checks"):
            if not isinstance(bundle.get(field), list) or len(bundle[field]) > 30 or any(not isinstance(item, str) or len(item) > 8000 for item in bundle[field]):
                raise ValueError("Research explanations must be bounded readable text.")
        if bundle["status"] == "SUCCESS" and (not sources or any(source["status"] not in {"SUCCESS", "EMPTY"} for source in sources)):
            raise ValueError("A successful research run must contain only complete source checks.")
        if len(canonical(bundle).encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("Research result exceeds the pilot storage bounds.")

    def finish(self, run_id, lease_token, bundle, now=None):
        self._require_research()
        with self._session(write=True) as connection:
            now = _moment(now)
            row = self._sql(connection, "SELECT case_id,parcel_id,status,lease_token,bundle_json FROM pmi_research_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row or row[3] != lease_token:
                raise ValueError("This research lease is no longer valid.")
            self._validate_bundle(bundle, row[0], row[1])
            if row[2] != "RUNNING":
                if row[2] in RUN_STATUSES and row[4] == canonical(bundle):
                    return {"status": row[2], "run_id": run_id, "already_finished": True}
                raise ValueError("A finished research result cannot be replaced.")
            active, active_token, expires = self._sql(connection, "SELECT lease_run_id,lease_token,lease_until FROM pmi_research_control WHERE control_id=1").fetchone()
            if active != run_id or active_token != lease_token or not expires or _moment(expires) <= now:
                raise ValueError("This research lease expired before its result was saved.")
            # Ensure a source result never crosses a changed case/parcel linkage.
            document, _ = self._document(connection, row[0])
            if document["baseline"]["parcel_id"] != row[1]:
                raise ValueError("The property's saved parcel linkage changed during research.")
            snapshots = 0
            for source in bundle["sources"]:
                if source["status"] not in {"SUCCESS", "EMPTY"}:
                    continue
                content_hash = digest(source.get("records", []))
                source_doc = copy.deepcopy(source)
                source_doc["content_hash"] = content_hash
                snapshot_id = digest({"case_id": row[0], "parcel_id": row[1], "source_key": source["source_key"], "content_hash": content_hash})
                cursor = self._sql(connection, "INSERT INTO pmi_research_snapshots(snapshot_id,case_id,parcel_id,source_key,content_hash,source_json,first_checked_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(snapshot_id) DO NOTHING", (snapshot_id, row[0], row[1], source["source_key"], content_hash, canonical(source_doc), _stamp(now)))
                snapshots += max(cursor.rowcount, 0)
                self._sql(connection, "INSERT INTO pmi_research_sources(case_id,source_key,snapshot_id,checked_at,source_json) VALUES(?,?,?,?,?) ON CONFLICT(case_id,source_key) DO UPDATE SET snapshot_id=excluded.snapshot_id,checked_at=excluded.checked_at,source_json=excluded.source_json", (row[0], source["source_key"], snapshot_id, _stamp(now), canonical(source_doc)))
            self._sql(connection, "UPDATE pmi_research_runs SET status=?,completed_at=?,bundle_json=? WHERE run_id=?", (bundle["status"], _stamp(now), canonical(bundle), run_id))
            delay = SUCCESS_SECONDS if bundle["status"] == "SUCCESS" else RETRY_SECONDS
            self._sql(connection, "UPDATE pmi_research_schedule SET last_completed_at=?,next_due_at=? WHERE case_id=?", (_stamp(now), _stamp(now + timedelta(seconds=delay)), row[0]))
            self._sql(connection, "UPDATE pmi_research_control SET lease_run_id=NULL,lease_token=NULL,lease_until=NULL WHERE control_id=1")
            self._append(connection, row[0], "RESEARCH", {"run_id": run_id, "status": bundle["status"],
                         "checked_at": _stamp(now), "source_statuses": {source["source_key"]: source["status"] for source in bundle["sources"]},
                         "summary": bundle.get("change_summary", "Official record check saved."),
                         "actor": "CC official-record researcher", "seller_intent_inferred": False}, run_id)
        return {"status": bundle["status"], "run_id": run_id, "new_snapshots": snapshots,
                "already_finished": False}
