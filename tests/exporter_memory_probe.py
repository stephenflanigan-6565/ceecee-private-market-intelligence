"""Synthetic, disk-backed fake Drive; measures two real exporter processes.

No requests go to Google. RSS is observed, not a production memory guarantee.
"""
import argparse
import gc
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import psutil


def imports(root):
    sys.path[:0] = [str(root), str(Path(root) / "tests")]


def worker(root, dsn, files, result, gate, fail):
    imports(root)
    from pmi_drive_export_service import DriveExportService
    from test_exporter_interruption import ENV
    from pmi_google_drive import DriveError, MAX_ARTIFACT_BYTES
    stages = []
    class DiskDrive:
        def identity(self):
            stages.append(["identity", psutil.Process().memory_info().rss])
            return {"principal_id": "synthetic"}
        def ensure_private_folder(self, *args):
            return {"id": "synthetic-folder"}
        def upload(self, folder, name, mime, content, export_id, kind):
            stages.append(["upload-" + kind, psutil.Process().memory_info().rss])
            if len(content) > MAX_ARTIFACT_BYTES:
                raise DriveError("artifact_too_large")
            if fail and kind == "summary":
                raise DriveError("drive_http_error", 503)
            Path(files, kind).write_bytes(content)
            return {"id": kind}
        def download(self, key):
            stages.append(["download-" + key, psutil.Process().memory_info().rss])
            return Path(files, key).read_bytes()
        def verify_private_folder(self, key):
            stages.append(["verified", psutil.Process().memory_info().rss])
            return {"id": key}
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stopped = threading.Event()
    def sample():
        while not stopped.wait(.005):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=sample)
    thread.start()
    service = DriveExportService(dsn, environment=ENV, client_factory=DiskDrive)
    gate.wait(30)
    started = time.monotonic()
    answer = service.poll("synthetic-memory-worker")
    stopped.set(); thread.join()
    Path(result).write_text(json.dumps({"outcome": answer, "seconds": time.monotonic()-started,
        "peak_rss_bytes": peak[0], "stages": stages, "status": service.status()}))


def main(root, notes, fail):
    imports(root)
    from test_exporter_interruption import InterruptionSQLite
    from test_research_store import pilot_payload
    from pmi_review_store import ReviewStore
    fixture = InterruptionSQLite()
    fixture.setUp()
    try:
        fixture.store.import_payload(pilot_payload(194), "synthetic-operator")
        ids = [c["case_id"] for c in fixture.store.list_cases()]
        with fixture.store._session(write=True) as c:
            for n in range(notes):
                fixture.store._sql(c, "INSERT INTO pmi_review_events VALUES(?,?,?,?,?)", (
                    "stress-note-"+str(n), ids[n % len(ids)], "STATE",
                    json.dumps({"state": "NEW", "note": "SYNTHETIC " + str(n) + " x"*2048}),
                    "2026-10-18T00:00:00+00:00"))
        snapshot = fixture.store.research_export_snapshot()
        counts = snapshot["manifest"]["source_counts"]
        del snapshot
        gc.collect()
        with tempfile.TemporaryDirectory() as folder:
            ctx = mp.get_context("spawn")
            gate = ctx.Event()
            processes = [ctx.Process(target=worker, args=(root, fixture.dsn, folder,
                str(Path(folder, str(i)+".json")), gate, fail)) for i in range(2)]
            for process in processes: process.start()
            gate.set()
            peak_sum = 0
            deadline = time.monotonic()+120
            while any(p.is_alive() for p in processes) and time.monotonic()<deadline:
                rss = 0
                for p in processes:
                    try: rss += psutil.Process(p.pid).memory_info().rss
                    except psutil.NoSuchProcess: pass
                peak_sum = max(peak_sum, rss)
                time.sleep(.01)
            for p in processes:
                if p.is_alive(): p.terminate()
                p.join()
            rows = [json.loads(Path(folder, str(i)+".json").read_text()) for i in range(2)]
            print(json.dumps({"notes": notes, "failed_summary_upload": fail,
                "source_counts": counts, "workers": rows, "peak_two_workers_rss_bytes": peak_sum,
                "artifact_bytes": Path(folder, "json").stat().st_size if Path(folder, "json").exists() else None,
                "exitcodes": [p.exitcode for p in processes],
                "measurement": "10ms aggregate RSS; 5ms per worker; excludes fixture generator and DB server; disk fake Drive"}))
            assert all(p.exitcode == 0 for p in processes)
            statuses = sorted(r["outcome"]["status"] for r in rows)
            assert statuses == sorted(["BUSY", "FAILED" if fail else "VERIFIED"]), statuses
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--notes", type=int, default=1000)
    parser.add_argument("--fail", action="store_true")
    args=parser.parse_args()
    main(args.root, args.notes, args.fail)
