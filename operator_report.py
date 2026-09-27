
#!/usr/bin/env python3
from db import connect
import sqlite3, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"

def scalar(c, sql, params=()):
    try:
        r=c.execute(sql,params).fetchone()
        return int(r[0] or 0)
    except sqlite3.Error:
        return 0

def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    counts={}
    for s in ("IGNORE","WATCH","INVESTIGATE","LATENT","ACTIVE"):
        counts[s]=scalar(c,"select count(*) from opportunities where upper(state)=?",(s,))
    eligible=scalar(c, """select count(*) from contact_governor
        where compliance_state='PASS' and outreach_authorized=1
        and governor_decision='CONTACT' and trim(coalesce(why_now,''))<>''""")
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat()
    failures=scalar(c,"select count(*) from runtime_runs where status='FAILED' and started_at>=?",(cutoff,))
    adapters=[]
    try:
        adapters=[dict(zip(("adapter","category","enabled","paid","status"),r))
                  for r in c.execute("select adapter_key,category,enabled,paid,status from adapter_registry order by adapter_key")]
    except sqlite3.Error: pass
    payload={"opportunities":counts,"contact_eligible":eligible,"failures_24h":failures,"adapters":adapters}
    now=datetime.now(timezone.utc).isoformat()
    c.execute("""insert into operator_snapshots(generated_at,ignore_count,watch_count,investigate_count,
      latent_count,active_count,contact_eligible_count,failures_24h,payload) values(?,?,?,?,?,?,?,?,?)""",
      (now,counts["IGNORE"],counts["WATCH"],counts["INVESTIGATE"],counts["LATENT"],counts["ACTIVE"],
       eligible,failures,json.dumps(payload)))
    c.commit()
    print(json.dumps({"generated_at":now,**payload},indent=2))
    c.close()
if __name__=="__main__": main()
