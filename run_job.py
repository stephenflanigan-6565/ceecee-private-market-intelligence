
#!/usr/bin/env python3
"""Retry/log wrapper for scheduled jobs. No outreach jobs are exposed here."""
from db import connect, insert_id
import subprocess, sys, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from runtime_config import CFG

ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"
ALLOWED={
 "scheduler":"scheduler_policy.py",
 "adapters":"adapter_registry.py",
 "governor":"contact_governor.py",
 "report":"operator_report.py",
}
def utc(): return datetime.now(timezone.utc).isoformat()
def main():
    if len(sys.argv)!=2 or sys.argv[1] not in ALLOWED:
        raise SystemExit("Usage: run_job.py ["+"|".join(ALLOWED)+"]")
    job=sys.argv[1]; key=str(uuid.uuid4())
    c=connect(); c.executescript((ROOT/"schema.sql").read_text()); c.commit()
    last=""
    for attempt in range(1,CFG.max_retries+1):
        started=utc()
        rid=insert_id(c,"insert into runtime_runs(run_key,job_name,started_at,status,attempt) values(?,?,?,\'RUNNING\',?)",(key,job,started,attempt)); c.commit()
        p=subprocess.run([sys.executable,str(ROOT/ALLOWED[job])],capture_output=True,text=True)
        last=(p.stderr or p.stdout)[-4000:]
        c.execute("update runtime_runs set finished_at=?,status=?,error_text=? where id=?",
                  (utc(),"SUCCESS" if p.returncode==0 else "FAILED",None if p.returncode==0 else last,rid)); c.commit()
        if p.returncode==0:
            print(p.stdout); c.close(); return
    c.close(); raise SystemExit(last or f"{job} failed")
if __name__=="__main__": main()
