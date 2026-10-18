"""Synthetic-only crash/locking checks; no Google or production connections."""
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from pmi_drive_export_service import DriveExportService, LEASE_SECONDS
from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from test_drive_export_service import FakeDrive
from test_research_export_snapshot import ResearchExportSnapshotTests

ENV = {"PMI_GOOGLE_DRIVE_CLIENT_ID": "synthetic-client",
       "PMI_GOOGLE_DRIVE_CLIENT_SECRET": "synthetic-secret",
       "PMI_GOOGLE_DRIVE_REFRESH_TOKEN": "synthetic-refresh"}


def crash_worker(dsn, marker, stage):
    service = DriveExportService(dsn, environment=ENV, client_factory=FakeDrive)
    def block(*args, **kwargs):
        Path(marker).write_text("entered", encoding="utf-8")
        time.sleep(60)
    if stage == "snapshot":
        import pmi_backup_parts
        pmi_backup_parts.build_package = block
    else:
        client = FakeDrive()
        client.identity = block
        service.client_factory = lambda: client
    service.poll("synthetic-crash-worker")


def second_worker(dsn, result):
    service = DriveExportService(dsn, environment=ENV, client_factory=FakeDrive)
    Path(result).write_text(json.dumps(service.poll("synthetic-second-worker")))


class InterruptionSQLite(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dsn = str(Path(self.temp.name) / "synthetic.sqlite")
        self.seed()

    def seed(self):
        # Reuse the full-history fixture: versions, notes, evidence, corrected
        # reviews, research runs, old snapshots and current source pointers.
        fixture = ResearchExportSnapshotTests()
        fixture.path = self.dsn
        fixture.review = ReviewStore(self.dsn)
        fixture.research = ResearchStore(self.dsn)
        fixture.now = datetime.now(timezone.utc)
        fixture.test_full_history_sources_reviews_corrections_and_exact_notes_retained()
        self.store = fixture.review
        self.client = FakeDrive()
        self.service = DriveExportService(self.dsn, environment=ENV, client_factory=lambda: self.client)

    def test_full_history_reopens_and_preserves_source(self):
        before = self.store.research_export_snapshot()
        self.assertEqual(self.service.poll()["status"], "VERIFIED")
        from pmi_backup_parts import validate_manifest
        manifest = json.loads(next(f["content"] for f in self.client.files.values() if f["kind"] == "manifest"))
        validate_manifest(manifest)
        self.assertEqual({t: entry["count"] for t, entry in manifest["tables"].items()}, before["manifest"]["source_counts"])
        self.assertEqual(self.store.research_export_snapshot()["source_revision"], before["source_revision"])

    def crash_check(self, stage):
        marker = str(Path(self.temp.name) / (stage + "-entered"))
        result = str(Path(self.temp.name) / (stage + "-second.json"))
        ctx = mp.get_context("spawn")
        first = ctx.Process(target=crash_worker, args=(self.dsn, marker, stage))
        first.start()
        try:
            deadline = time.monotonic() + 20
            while not Path(marker).exists() and first.is_alive() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(Path(marker).exists(), "first worker did not reach fault point")
            other = ctx.Process(target=second_worker, args=(self.dsn, result))
            other.start()
            other.join(20)
            if other.is_alive():
                other.terminate(); other.join()
                self.fail("second worker blocked instead of returning BUSY")
            self.assertEqual(other.exitcode, 0)
            self.assertEqual(json.loads(Path(result).read_text())["status"], "BUSY")
            # Real process death: no except/finally in worker is allowed to run.
            first.terminate()
            first.join(10)
            self.assertFalse(first.is_alive())
            self.assertEqual(self.service.status()["status"], "RUNNING")
            self.assertEqual(self.service.poll()["status"], "BUSY")
            future = datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS + 5)
            self.service.clock = lambda: future
            self.assertEqual(self.service.status()["status"], "INTERRUPTED")
            self.assertEqual(self.service.poll()["status"], "VERIFIED")
            self.assertEqual(self.client.created, 3)
        finally:
            if first.is_alive():
                first.terminate(); first.join(10)

    def test_killed_snapshot_has_durable_receipt_and_recovers(self):
        self.crash_check("snapshot")

    def test_killed_identity_has_durable_receipt_and_recovers(self):
        self.crash_check("identity")

    def test_failed_upload_retry_does_not_duplicate_artifacts(self):
        self.client.fail_summary_once = True
        self.assertEqual(self.service.poll()["status"], "FAILED")
        self.assertEqual(self.service.status()["failure_stage"], "upload_readback")
        self.assertEqual(self.service.poll()["status"], "RETRY_WAIT")
        self.assertEqual(self.service.poll(force=True)["status"], "VERIFIED")
        self.assertEqual(self.client.created, 3)
        self.assertNotIn("private-refresh-token", str(self.service._rows()))

    def test_snapshot_error_reports_stage_without_sensitive_message(self):
        with patch("pmi_backup_parts.build_package", side_effect=ValueError("synthetic-secret raw failure")):
            service = DriveExportService(self.dsn, store=self.store, environment=ENV, client_factory=FakeDrive)
            self.assertEqual(service.poll()["status"], "FAILED")
        state = self.service.status()
        self.assertEqual(state["failure_stage"], "snapshot")
        self.assertEqual(state["error_code"], "SNAPSHOT_VALIDATION_FAILED")
        self.assertNotIn("synthetic-secret", str(self.service._rows()))

    def test_receipt_write_failure_prevents_external_work(self):
        with patch.object(self.service, "_append", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.service.poll()
        self.assertEqual(self.client.identities, 0)


@unittest.skipUnless(os.getenv("PMI_EXPORT_TEST_PG") == "1", "disposable PostgreSQL not configured")
class InterruptionPostgres(InterruptionSQLite):
    def setUp(self):
        import psycopg
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Fixed CI-only loopback target. Never uses DATABASE_URL.
        self.dsn = "postgresql://pmi_test:disposable_test_only@127.0.0.1:5432/pmi_export_synthetic"
        with psycopg.connect(self.dsn, autocommit=True) as c:
            c.execute("DROP SCHEMA public CASCADE")
            c.execute("CREATE SCHEMA public")
        self.seed()


if __name__ == "__main__":
    unittest.main()
