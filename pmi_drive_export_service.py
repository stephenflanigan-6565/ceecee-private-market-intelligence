"""Verified private Drive exports, coordinated in the existing review ledger.

No schema is created and no property, review, evidence, research or learning
record is modified. Daily scheduling is gated by an actual upload/readback.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import uuid

from pmi_review_store import ReviewStore

FORMAT_VERSION = "PMI_DAILY_RESEARCH_EXPORT_V1"
CASE_ID = "workspace:drive-export"
LOCK_ID = 73421629
LEASE_SECONDS = 600
RETRY_SECONDS = 6 * 60 * 60
CREDENTIAL_KEYS = ("PMI_GOOGLE_DRIVE_CLIENT_ID", "PMI_GOOGLE_DRIVE_CLIENT_SECRET",
                   "PMI_GOOGLE_DRIVE_REFRESH_TOKEN")
SAFE_DRIVE_ERRORS = frozenset({
    "invalid_file_id", "drive_credentials_missing", "invalid_timeout",
    "drive_http_error", "redirect_not_allowed", "invalid_content_length",
    "response_too_large", "drive_transport_error", "invalid_drive_response",
    "invalid_oauth_response", "unexpected_oauth_scope", "drive_identity_unavailable",
    "drive_not_owner", "privacy_verification_failed", "drive_not_private",
    "invalid_report_folder", "folder_not_app_managed", "drive_lookup_incomplete",
    "invalid_folder_name", "ambiguous_report_folder", "invalid_artifact",
    "artifact_too_large", "invalid_artifact_identity", "ambiguous_artifact",
    "artifact_metadata_mismatch", "artifact_unavailable", "retained_payload_budget_exceeded",
})


def _instant(value=None):
    value = datetime.now(timezone.utc) if value is None else value
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Export clock requires an aware timestamp")
    return value.astimezone(timezone.utc)


def _stamp(value):
    return _instant(value).isoformat()


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _client_from_environment(environment=None):
    from pmi_google_drive import GoogleDriveClient
    return GoogleDriveClient.from_environment(environ=environment)


class DriveExportService:
    def __init__(self, dsn, *, client_factory=None, store=None, clock=None,
                 environment=None):
        self.store = store if store is not None else ReviewStore(dsn)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.environment = os.environ if environment is None else environment
        self.client_factory = client_factory or (lambda: _client_from_environment(self.environment))

    def _configured(self):
        return all(isinstance(self.environment.get(key), str) and self.environment[key].strip()
                   for key in CREDENTIAL_KEYS)

    def _config_digest(self):
        # The digest detects a changed credential identity without persisting
        # any credential. The verified receipt separately binds actual owner
        # identity, private folder and export format.
        return _hash(_bytes({"credentials": [self.environment.get(key, "") for key in CREDENTIAL_KEYS],
                             "folder_id": self.environment.get("PMI_GOOGLE_DRIVE_FOLDER_ID") or None,
                             "format": FORMAT_VERSION}))

    def _rows(self):
        with self.store._session() as connection:
            rows = self.store._sql(connection, "SELECT data_json FROM pmi_ai_review_records WHERE case_id=? ORDER BY recorded_at,record_key", (CASE_ID,)).fetchall()
        output = [json.loads(row[0]) for row in rows]
        return sorted((row for row in output if row.get("kind", "").startswith("DRIVE_EXPORT_")),
                      key=lambda row: row.get("sequence", 0))

    def _append(self, kind, payload, now):
        with self.store._session(write=True) as connection:
            sequence = self.store._sql(connection, "SELECT COUNT(*) FROM pmi_ai_review_records WHERE case_id=?", (CASE_ID,)).fetchone()[0] + 1
            document = {**payload, "kind": kind, "sequence": sequence, "recorded_at": _stamp(now)}
            key = "drive-export:" + uuid.uuid4().hex
            self.store._sql(connection, "INSERT INTO pmi_ai_review_records(record_key,kind,case_id,analysis_id,data_json,recorded_at) VALUES(?,?,?,?,?,?)", (key, kind, CASE_ID, "", _bytes(document).decode("utf-8"), _stamp(now)))
        return document

    @contextmanager
    def _coordination(self):
        """A separate session lock never holds the workspace write lock."""
        if self.store.postgres:
            connection = self.store._connect(write=True)
            acquired = False
            try:
                acquired = bool(self.store._sql(connection, "SELECT pg_try_advisory_lock(?)", (LOCK_ID,)).fetchone()[0])
                connection.commit()
                yield acquired
            finally:
                # Closing the dedicated session releases its advisory lock,
                # including after an error. No transaction spans Drive I/O.
                connection.close()
        else:
            # SQLite is used only for isolated previews/tests. Lock the
            # existing database inode without creating another file/table.
            import fcntl
            with open(self.store.path, "rb") as file:
                acquired = False
                try:
                    try:
                        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                    except BlockingIOError:
                        pass
                    yield acquired
                finally:
                    if acquired:
                        fcntl.flock(file.fileno(), fcntl.LOCK_UN)

    def _state(self, rows, config_digest):
        matches = [row for row in rows if row.get("config_digest") == config_digest]
        last = matches[-1] if matches else None
        verified = next((row for row in reversed(matches) if row["kind"] == "DRIVE_EXPORT_VERIFIED"), None)
        invalidated = any(row.get("gate_invalidated") and (verified is None or row["sequence"] > verified["sequence"])
                          for row in matches)
        if verified is not None and (verified.get("format") != FORMAT_VERSION or not verified.get("target_fingerprint") or invalidated):
            verified = None
        return last, verified

    def status(self):
        """Read durable status without connecting to Drive or writing data."""
        base = {"status": "UNCONFIGURED" if not self._configured() else "WAITING",
                "daily_enabled": False, "bootstrap_verified": False,
                "last_successful_export_at": None, "next_due_at": None,
                "last_outcome": None, "json_url": None, "summary_url": None,
                "source_counts": None, "exported_counts": None, "review_counts": None}
        if not self.store.ready():
            return base
        rows = self._rows()
        last, verified = self._state(rows, self._config_digest())
        # Retain prior successful references when configuration is absent or
        # changed, but never inherit its scheduling gate.
        historical = verified or next((row for row in reversed(rows) if row["kind"] == "DRIVE_EXPORT_VERIFIED"), None)
        if historical:
            base.update({key: historical.get(key) for key in ("json_url", "summary_url", "source_counts", "exported_counts", "review_counts")})
            base["last_successful_export_at"] = historical.get("verified_at")
        if not self._configured():
            return base
        if verified:
            base.update({"status": "ENABLED", "daily_enabled": True,
                         "bootstrap_verified": True, "next_due_at": verified["next_due_at"]})
        elif last:
            base["status"] = {"DRIVE_EXPORT_RUNNING": "RUNNING", "DRIVE_EXPORT_FAILED": "FAILED"}.get(last["kind"], "WAITING")
        if last:
            base["last_outcome"] = last.get("outcome")
            if last["kind"] == "DRIVE_EXPORT_FAILED":
                base["status"] = "FAILED"
                base["retry_after"] = last.get("retry_after")
                base["failure_stage"] = last.get("failure_stage")
                base["error_code"] = last.get("error_code")
                base["http_status"] = last.get("http_status")
            if last["kind"] == "DRIVE_EXPORT_RUNNING":
                base["lease_until"] = last.get("lease_until")
                base["status"] = "RUNNING" if _instant(last["lease_until"]) > _instant(self.clock()) else "INTERRUPTED"
        return base

    def poll(self, worker_id=None, *, force=False):
        """Attempt the first verified export, then one export per 24 hours."""
        if not self._configured():
            return {"status": "UNCONFIGURED", "daily_enabled": False}
        if not self.store.ready():
            return {"status": "WAITING", "daily_enabled": False}
        now = _instant(self.clock())
        config_digest = self._config_digest()
        with self._coordination() as acquired:
            if not acquired:
                return {"status": "BUSY"}
            rows = self._rows()
            last, verified = self._state(rows, config_digest)
            if last and last["kind"] == "DRIVE_EXPORT_RUNNING" and _instant(last["lease_until"]) > now:
                return {"status": "BUSY", "daily_enabled": bool(verified)}
            if not force and last and last["kind"] == "DRIVE_EXPORT_FAILED" and _instant(last["retry_after"]) > now:
                return {"status": "RETRY_WAIT", "daily_enabled": bool(verified)}
            if verified and _instant(verified["next_due_at"]) > now:
                return {"status": "IDLE", "daily_enabled": True}
            run_id = "drive_" + uuid.uuid4().hex
            phase = "identity"
            # Persist the attempt before identity, snapshot construction or JSON
            # serialization. Abrupt process death must leave a bounded lease
            # and an INTERRUPTED status, not look like an export never started.
            # Fail closed if this durable write fails: do not contact Drive.
            claim = self._append("DRIVE_EXPORT_RUNNING", {
                "outcome": "RUNNING", "run_id": run_id,
                "worker_id": worker_id or "manual", "mode": "DAILY" if verified else "BOOTSTRAP",
                "config_digest": config_digest, "format": FORMAT_VERSION,
                "lease_until": _stamp(now + timedelta(seconds=LEASE_SECONDS)),
            }, now)
            try:
                client = self.client_factory()
                identity = client.identity()
                principal_id = identity["principal_id"]
                if not isinstance(principal_id, str) or not principal_id:
                    raise ValueError("Drive principal unavailable")
                phase = "folder"
                requested_folder = self.environment.get("PMI_GOOGLE_DRIVE_FOLDER_ID") or None
                if requested_folder is None and last and last.get("principal_id") == principal_id:
                    requested_folder = last.get("folder_id")
                folder = client.ensure_private_folder("PMI Research Reports", requested_folder)
                folder_id = folder["id"]
                target_fingerprint = _hash(_bytes({"principal": principal_id, "folder": folder_id, "format": FORMAT_VERSION}))
                if verified and verified["target_fingerprint"] != target_fingerprint:
                    verified = None
                phase = "resource_preflight"
                from pmi_export_budget import check_retained_payload_budget
                check_retained_payload_budget(self.store)
                phase = "snapshot"
                from pmi_research_export import validate_snapshot, build_summary
                snapshot = self.store.research_export_snapshot()
                validate_snapshot(snapshot)
                completed_exports = {row.get("export_id") for row in rows if row["kind"] == "DRIVE_EXPORT_VERIFIED"}
                prior = next((row for row in reversed(rows) if row.get("config_digest") == config_digest and row.get("target_fingerprint") == target_fingerprint and row.get("source_revision") == snapshot["source_revision"] and row.get("export_id") not in completed_exports and row.get("export_id")), None)
                artifact_at = _instant(prior["generated_at"]) if prior else now
                snapshot["generated_at"] = _stamp(artifact_at)
                day = artifact_at.date().isoformat()
                export_id = prior["export_id"] if prior else "pmi:" + _hash(_bytes({
                    "config": config_digest, "target": target_fingerprint,
                    "day": day, "source": snapshot["source_revision"],
                }))
                name = "PMI-Research-" + day + "-" + snapshot["source_revision"][:12]
                json_content = _bytes(snapshot)
                summary_content = build_summary(snapshot).encode("utf-8")
                claim = self._append("DRIVE_EXPORT_RUNNING", {
                    "outcome": "RUNNING", "run_id": run_id,
                    "worker_id": worker_id or "manual", "mode": "DAILY" if verified else "BOOTSTRAP",
                    "config_digest": config_digest, "target_fingerprint": target_fingerprint,
                    "principal_id": principal_id, "folder_id": folder_id,
                    "source_revision": snapshot["source_revision"], "export_id": export_id,
                    "generated_at": snapshot["generated_at"], "format": FORMAT_VERSION,
                    "lease_until": _stamp(now + timedelta(seconds=LEASE_SECONDS)),
                }, now)
                phase = "upload"
                json_file = client.upload(folder_id, name + ".json", "application/json", json_content, export_id, "json")
                summary_file = client.upload(folder_id, name + ".md", "text/markdown", summary_content, export_id, "summary")
                phase = "readback"
                read_json = client.download(json_file["id"])
                read_summary = client.download(summary_file["id"])
                if not isinstance(read_json, bytes) or _hash(read_json) != _hash(json_content):
                    raise ValueError("JSON readback mismatch")
                restored = json.loads(read_json.decode("utf-8"))
                validate_snapshot(restored)
                if restored["manifest"]["source_counts"] != snapshot["manifest"]["source_counts"] or restored["manifest"]["exported_counts"] != snapshot["manifest"]["exported_counts"]:
                    raise ValueError("Readback reconciliation mismatch")
                if read_summary != summary_content:
                    raise ValueError("Summary readback mismatch")
                phase = "folder_readback"
                checked_folder = client.verify_private_folder(folder_id)
                if checked_folder["id"] != folder_id:
                    raise ValueError("Private folder readback mismatch")
                completed_at = _instant(self.clock())
                receipt = self._append("DRIVE_EXPORT_VERIFIED", {
                    **{key: value for key, value in claim.items() if key not in {"kind", "sequence", "recorded_at", "lease_until"}},
                    "outcome": "VERIFIED", "verified_at": _stamp(completed_at),
                    "next_due_at": _stamp(completed_at + timedelta(hours=24)),
                    "daily_enabled": True,
                    "json_id": json_file["id"], "json_url": json_file.get("webViewLink"),
                    "summary_id": summary_file["id"], "summary_url": summary_file.get("webViewLink"),
                    "json_sha256": _hash(json_content), "summary_sha256": _hash(summary_content),
                    "source_counts": snapshot["manifest"]["source_counts"],
                    "exported_counts": snapshot["manifest"]["exported_counts"],
                    "review_counts": snapshot["review_counts"],
                }, completed_at)
                return {"status": "VERIFIED", "daily_enabled": True,
                        "verified_at": receipt["verified_at"], "next_due_at": receipt["next_due_at"]}
            except Exception as error:
                # Never save OAuth responses, exception text or credentials.
                failed_at = _instant(self.clock())
                from pmi_google_drive import DriveError
                error_code = "EXPORT_VERIFICATION_FAILED" if phase in {"readback", "folder_readback"} else "EXPORT_FAILED"
                http_status = None
                if isinstance(error, DriveError):
                    if error.code in SAFE_DRIVE_ERRORS:
                        error_code = error.code
                    if type(error.http_status) is int and 100 <= error.http_status <= 599:
                        http_status = error.http_status
                elif isinstance(error, ValueError) and phase == "snapshot":
                    error_code = "SNAPSHOT_VALIDATION_FAILED"
                detail = {key: value for key, value in (claim or {}).items() if key not in {"kind", "sequence", "recorded_at", "lease_until"}}
                self._append("DRIVE_EXPORT_FAILED", {
                    **detail, "run_id": run_id, "config_digest": config_digest,
                    "outcome": "FAILED", "failure_stage": phase,
                    "error_code": error_code, "http_status": http_status,
                    "gate_invalidated": phase in {"folder", "folder_readback"},
                    "retry_after": _stamp(failed_at + timedelta(seconds=RETRY_SECONDS)),
                }, failed_at)
                return {"status": "FAILED", "daily_enabled": bool(verified) and phase not in {"folder", "folder_readback"}}
