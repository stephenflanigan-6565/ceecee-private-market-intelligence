#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from db import connect, backend, execute, executescript

ROOT = Path(__file__).resolve().parent

def scalar(c, query, params=()):
    try:
        row = execute(c, query, params).fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        return 0

def build_snapshot(write_snapshot=True):
    c = connect()
    schema = (ROOT / ("schema_postgres.sql" if backend()=="postgres" else "schema.sql")).read_text()
    executescript(c, schema)
    c.commit()

    counts = {s: scalar(c, "select count(*) from opportunities where upper(state)=?", (s,))
              for s in ("IGNORE","WATCH","INVESTIGATE","LATENT","ACTIVE")}
    eligible = scalar(c, """select count(*) from contact_governor
        where compliance_state='PASS' and outreach_authorized=1
        and governor_decision='CONTACT' and trim(coalesce(why_now,''))<>''""")
    cutoff = (datetime.now(timezone.utc)-timedelta(hours=24)).isoformat()
    failures = scalar(c, "select count(*) from runtime_runs where status='FAILED' and started_at>=?", (cutoff,))

    adapters=[]
    try:
        rows=execute(c, "select adapter_key,category,enabled,paid,status from adapter_registry order by adapter_key").fetchall()
        adapters=[{"adapter":r[0],"category":r[1],"enabled":bool(r[2]),"paid":bool(r[3]),"status":r[4]} for r in rows]
    except Exception:
        pass

    now=datetime.now(timezone.utc).isoformat()
    payload={"generated_at":now,"database_backend":backend(),"opportunities":counts,
             "contact_eligible":eligible,"failures_24h":failures,"adapters":adapters}
    if write_snapshot:
        execute(c, """insert into operator_snapshots(generated_at,ignore_count,watch_count,investigate_count,
          latent_count,active_count,contact_eligible_count,failures_24h,payload) values(?,?,?,?,?,?,?,?,?)""",
          (now,counts["IGNORE"],counts["WATCH"],counts["INVESTIGATE"],counts["LATENT"],counts["ACTIVE"],
           eligible,failures,json.dumps(payload)))
        c.commit()
    c.close()
    return payload

def main():
    print(json.dumps(build_snapshot(True), indent=2))

if __name__=="__main__":
    main()
