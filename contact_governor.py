#!/usr/bin/env python3
"""Contact Governor: opportunities do not become outreach merely because signals exist."""
from db import connect
import sqlite3, json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"
def utc(): return datetime.now(timezone.utc).isoformat()
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    for pid,state,why,n in c.execute("select parcel_id,state,why_now,independent_signal_types from opportunities").fetchall():
        evidence=[r[0] for r in c.execute("select distinct signal_type from signals where parcel_id=? and active=1",(pid,))]
        # Signals can elevate research, never self-authorize contact.
        decision="RESEARCH" if state=="INVESTIGATE" else "NO_CONTACT"
        c.execute("""insert into contact_governor(parcel_id,opportunity_state,why_now,evidence_summary,governor_decision,updated_at)
          values(?,?,?,?,?,?) on conflict(parcel_id) do update set opportunity_state=excluded.opportunity_state,
          why_now=excluded.why_now,evidence_summary=excluded.evidence_summary,governor_decision=excluded.governor_decision,
          updated_at=excluded.updated_at""",(pid,state,why,json.dumps(evidence),decision,utc()))
    c.commit(); c.close()
if __name__=="__main__": main()
