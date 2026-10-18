"""Full synthetic upload/readback, durable gating and worker coordination."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from pmi_drive_export_service import DriveExportService, CASE_ID, LEASE_SECONDS
from pmi_google_drive import DriveError, GoogleDriveClient
from pmi_research_export import validate_snapshot
from pmi_research_store import ResearchStore
from pmi_review_store import ReviewStore
from test_research_store import pilot_payload
from test_google_drive_client import FakeGoogle


class FakeDrive:
    def __init__(self):
        self.principal = "google-drive:synthetic-principal"
        self.files = {}
        self.identities = 0
        self.created = 0
        self.fail_summary_once = False
        self.corrupt = None
        self.upload_hook = None
        self.private = True
        self.operations = []

    def identity(self):
        self.identities += 1
        return {"principal_id": self.principal}

    def ensure_private_folder(self, name, folder_id):
        self.operations.append("folder")
        if not self.private:
            raise RuntimeError("private-token-invalid-folder")
        return {"id": folder_id or "private-folder", "webViewLink": "https://drive.example.test/private-folder"}

    def upload(self, folder_id, name, mime_type, content, export_id, artifact_kind):
        self.operations.append("upload:" + artifact_kind)
        if self.upload_hook:
            self.upload_hook()
        if artifact_kind == "summary" and self.fail_summary_once:
            self.fail_summary_once = False
            raise RuntimeError("private-refresh-token-network-failure")
        identity = (folder_id, export_id, artifact_kind)
        if identity not in self.files:
            self.created += 1
            self.files[identity] = {"id": "file-" + str(self.created), "content": content,
                                    "kind": artifact_kind, "name": name}
        saved = self.files[identity]
        return {"id": saved["id"], "webViewLink": "https://drive.example.test/" + saved["id"]}

    def download(self, file_id):
        item = next(item for item in self.files.values() if item["id"] == file_id)
        self.operations.append("download:" + item["kind"])
        return item["content"] + b" " if self.corrupt == item["kind"] else item["content"]

    def verify_private_folder(self, folder_id):
        self.operations.append("verify-folder")
        if not self.private:
            raise RuntimeError("private-folder-not-private")
        return {"id": folder_id}


class DriveExportServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "export.sqlite")
        self.review = ReviewStore(self.path)
        self.research = ResearchStore(self.path)
        self.now = datetime(2026, 10, 12, 3, 0, tzinfo=timezone.utc)
        self.env = {"PMI_GOOGLE_DRIVE_CLIENT_ID": "synthetic-client",
                    "PMI_GOOGLE_DRIVE_CLIENT_SECRET": "secret-not-written",
                    "PMI_GOOGLE_DRIVE_REFRESH_TOKEN": "refresh-not-written"}
        self.client = FakeDrive()
        self.service = DriveExportService(self.path, client_factory=lambda: self.client,
                                          clock=lambda: self.now, environment=self.env)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        self.review.initialize()
        self.review.import_payload(pilot_payload(2), "synthetic-operator")
        self.research.initialize()
        case = self.review.list_cases()[0]
        self.review.set_state(case["case_id"], "COMPLETE", "Synthetic reviewed property note", "synthetic-operator", "synthetic-note")

    def test_missing_configuration_is_no_network_no_storage_creation(self):
        self.env.clear()
        self.service.client_factory = lambda: self.fail("No network for missing credentials")
        self.assertEqual(self.service.poll()["status"], "UNCONFIGURED")
        self.assertEqual(self.service.status()["status"], "UNCONFIGURED")
        self.assertFalse(Path(self.path).exists())

    def test_missing_workspace_waits_without_initialization(self):
        self.service.client_factory = lambda: self.fail("No network for missing workspace")
        self.assertEqual(self.service.poll()["status"], "WAITING")
        self.assertFalse(Path(self.path).exists())

    def test_bootstrap_reads_both_artifacts_before_enabling_daily(self):
        self.load()
        before = self.review.research_export_snapshot()
        self.client.upload_hook = lambda: self.assertFalse(self.service.status()["daily_enabled"])
        result = self.service.poll("synthetic-worker")
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(self.client.operations, ["folder", "upload:json", "upload:summary", "download:json", "download:summary", "verify-folder"])
        status = self.service.status()
        self.assertTrue(status["daily_enabled"])
        self.assertTrue(status["bootstrap_verified"])
        self.assertEqual(status["source_counts"], status["exported_counts"])
        self.assertEqual(status["review_counts"]["properties_with_operator_work"], 1)
        self.assertEqual(status["next_due_at"], (self.now + timedelta(hours=24)).isoformat())
        restored = json.loads(next(item["content"] for item in self.client.files.values() if item["kind"] == "json"))
        validate_snapshot(restored)
        after = self.review.research_export_snapshot()
        self.assertEqual(before["source_revision"], after["source_revision"])
        self.assertEqual(before["manifest"], after["manifest"])
        self.assertEqual(before["cases"], after["cases"])
        self.assertTrue(all(row["kind"].startswith("DRIVE_EXPORT_") for row in self.service._rows()))
        self.assertNotIn("secret-not-written", str(self.service._rows()))
        self.assertNotIn("refresh-not-written", str(self.service._rows()))

    def test_partial_upload_reuses_immutable_content_and_file_identity(self):
        self.load()
        self.client.fail_summary_once = True
        self.assertEqual(self.service.poll()["status"], "FAILED")
        self.assertFalse(self.service.status()["daily_enabled"])
        self.assertEqual(self.client.created, 1)
        self.assertEqual(self.service.poll()["status"], "RETRY_WAIT")
        self.now += timedelta(hours=1)
        self.assertEqual(self.service.poll(force=True)["status"], "VERIFIED")
        self.assertEqual(self.client.created, 2)
        self.assertEqual(len(self.client.files), 2)
        receipts = self.service._rows()
        artifact_claim = next(row for row in receipts if row.get("export_id"))
        self.assertEqual(artifact_claim["export_id"], receipts[-1]["export_id"])
        self.assertEqual(artifact_claim["generated_at"], receipts[-1]["generated_at"])

    def test_readback_mismatch_cannot_enable_daily(self):
        for kind in ("json", "summary"):
            with self.subTest(kind=kind):
                if not self.review.ready():
                    self.load()
                self.client.corrupt = kind
                self.assertEqual(self.service.poll(force=True)["status"], "FAILED")
                self.assertFalse(self.service.status()["daily_enabled"])
                self.assertFalse(any(row["kind"] == "DRIVE_EXPORT_VERIFIED" for row in self.service._rows()))

    def test_durable_gate_skips_network_until_due_then_writes_new_day(self):
        self.load()
        self.assertEqual(self.service.poll()["status"], "VERIFIED")
        self.now += timedelta(hours=23)
        self.assertEqual(self.service.poll()["status"], "IDLE")
        self.assertEqual(self.client.identities, 1)
        self.assertEqual(self.service.poll(force=True)["status"], "IDLE")
        self.now += timedelta(hours=1)
        reloaded = DriveExportService(self.path, client_factory=lambda: self.client,
                                      clock=lambda: self.now, environment=self.env)
        self.assertEqual(reloaded.poll()["status"], "VERIFIED")
        self.assertEqual(self.client.created, 4)
        names = {item["name"] for item in self.client.files.values()}
        self.assertTrue(any("2026-10-12" in name for name in names))
        self.assertTrue(any("2026-10-13" in name for name in names))
        self.assertEqual(len({row["export_id"] for row in self.service._rows() if row["kind"] == "DRIVE_EXPORT_VERIFIED"}), 2)

    def test_changed_principal_or_target_requires_new_bootstrap(self):
        self.load()
        self.assertEqual(self.service.poll()["status"], "VERIFIED")
        self.env["PMI_GOOGLE_DRIVE_REFRESH_TOKEN"] = "different-synthetic-refresh"
        self.client.principal = "google-drive:different-principal"
        self.client.corrupt = "summary"
        self.assertFalse(self.service.status()["daily_enabled"])
        self.assertEqual(self.service.poll()["status"], "FAILED")
        self.assertFalse(self.service.status()["daily_enabled"])
        self.client.corrupt = None
        self.assertEqual(self.service.poll(force=True)["status"], "VERIFIED")
        self.env["PMI_GOOGLE_DRIVE_FOLDER_ID"] = "other-private-folder"
        self.assertFalse(self.service.status()["daily_enabled"])
        self.assertEqual(self.service.poll()["status"], "VERIFIED")
        self.assertEqual(self.service._rows()[-1]["folder_id"], "other-private-folder")

    def test_concurrent_poll_cannot_upload_while_first_worker_holds_claim(self):
        self.load()
        started, release = threading.Event(), threading.Event()
        calls = []

        def hook():
            calls.append("upload")
            if len(calls) == 1:
                started.set()
                self.assertTrue(release.wait(timeout=3))

        self.client.upload_hook = hook
        other = DriveExportService(self.path, client_factory=lambda: self.fail("Busy worker must not enter Drive"),
                                   clock=lambda: self.now, environment=self.env)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.service.poll, "worker-a")
            self.assertTrue(started.wait(timeout=3))
            try:
                self.assertEqual(other.poll("worker-b")["status"], "BUSY")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3)["status"], "VERIFIED")
        self.assertEqual(self.client.created, 2)

    def test_upload_holds_no_workspace_mutation_transaction(self):
        self.load()
        case = self.review.list_cases()[0]
        completed = []

        def hook():
            if completed:
                return
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.review.set_state, case["case_id"], "WAITING", "Concurrent synthetic operator note", "operator", "concurrent-export-note")
                future.result(timeout=3)
            completed.append(True)

        self.client.upload_hook = hook
        self.assertEqual(self.service.poll()["status"], "VERIFIED")
        self.assertEqual(self.review.case(case["case_id"])["state"], "WAITING")

    def test_durable_unexpired_lease_waits_then_recovers(self):
        self.load()
        self.service._append("DRIVE_EXPORT_RUNNING", {"config_digest": self.service._config_digest(),
                             "outcome": "RUNNING", "lease_until": (self.now + timedelta(seconds=LEASE_SECONDS)).isoformat()}, self.now)
        self.assertEqual(self.service.poll()["status"], "BUSY")
        self.assertEqual(self.client.identities, 0)
        self.now += timedelta(seconds=LEASE_SECONDS + 1)
        self.assertEqual(self.service.poll()["status"], "VERIFIED")

    def test_private_folder_failure_invalidates_previous_daily_gate(self):
        self.load()
        self.assertEqual(self.service.poll()["status"], "VERIFIED")
        self.now += timedelta(hours=24)
        self.client.private = False
        self.assertEqual(self.service.poll()["status"], "FAILED")
        self.assertFalse(self.service.status()["daily_enabled"])
        self.assertNotIn("private-token", str(self.service._rows()))

    def test_postgres_coordination_commits_before_drive_work_and_closes(self):
        store = Mock()
        store.postgres = True
        connection = Mock()
        store._connect.return_value = connection
        store._sql.return_value.fetchone.return_value = (True,)
        service = DriveExportService("unused", store=store, environment=self.env)
        with service._coordination() as acquired:
            self.assertTrue(acquired)
            connection.commit.assert_called_once()
            connection.close.assert_not_called()
        connection.close.assert_called_once()

    def test_real_client_http_transport_verifies_full_service_contract(self):
        self.load()
        server = FakeGoogle()
        client = GoogleDriveClient.from_environment(environ=self.env, opener=server)
        service = DriveExportService(self.path, client_factory=lambda: client,
                                    clock=lambda: self.now, environment=self.env)
        self.assertEqual(service.poll()["status"], "VERIFIED")
        self.assertTrue(service.status()["daily_enabled"])
        self.assertEqual(len(server.contents), 2)
        artifacts = [item for item in server.files.values() if item.get("appProperties", {}).get("export_id")]
        self.assertEqual(len(artifacts), 2)
        self.assertTrue(all(len(item["appProperties"]["export_id"].encode("utf-8")) <= 100 for item in artifacts))
        restored = json.loads(next(server.contents[item["id"]] for item in artifacts if item["appProperties"]["artifact_kind"] == "json"))
        validate_snapshot(restored)
        self.assertEqual(service.status()["source_counts"], restored["manifest"]["source_counts"])

    def test_safe_drive_failure_preserves_code_and_status_without_raw_details(self):
        self.load()
        self.client.identity = Mock(side_effect=DriveError("drive_http_error", 403))
        self.assertEqual(self.service.poll()["status"], "FAILED")
        status = self.service.status()
        self.assertEqual(status["failure_stage"], "identity")
        self.assertEqual(status["error_code"], "drive_http_error")
        self.assertEqual(status["http_status"], 403)
        self.assertFalse(status["daily_enabled"])

    def test_same_day_credential_rotation_verifies_new_immutable_artifacts(self):
        self.load()
        server = FakeGoogle()
        service = DriveExportService(self.path,
                    client_factory=lambda: GoogleDriveClient.from_environment(environ=self.env, opener=server),
                    clock=lambda: self.now, environment=self.env)
        self.assertEqual(service.poll()["status"], "VERIFIED")
        original_files = dict(server.contents)
        original_receipt = service._rows()[-1]
        self.now += timedelta(minutes=10)
        self.env["PMI_GOOGLE_DRIVE_CLIENT_SECRET"] = "rotated-synthetic-client-secret"
        self.assertFalse(service.status()["daily_enabled"])
        self.assertEqual(service.poll()["status"], "VERIFIED")
        rotated_receipt = service._rows()[-1]
        self.assertTrue(service.status()["daily_enabled"])
        self.assertEqual(original_receipt["source_revision"], rotated_receipt["source_revision"])
        self.assertEqual(original_receipt["target_fingerprint"], rotated_receipt["target_fingerprint"])
        self.assertNotEqual(original_receipt["config_digest"], rotated_receipt["config_digest"])
        self.assertNotEqual(original_receipt["export_id"], rotated_receipt["export_id"])
        self.assertEqual(len(server.contents), 4)
        for file_id, content in original_files.items():
            self.assertEqual(server.contents[file_id], content)


if __name__ == "__main__":
    unittest.main()
