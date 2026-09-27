#!/usr/bin/env python3
"""Source-aware scheduler policy. This file decides what is due; an OS/cloud scheduler invokes the actual jobs."""
from db import connect
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"
POLICY={
 "suffolk_parcel_owner":("DAILY",10,"Current parcel/owner state"),
 "suffolk_transfer":("DAILY",20,"Recorded transfer events"),
 "southampton_location":("MONTHLY",70,"Zoning/building/property context"),
 "historic_parcel":("MONTHLY",80,"Parcel lineage"),
 "assessment_roll":("ANNUAL_OR_PUBLICATION",90,"Refresh when new final roll is published"),
 "watch_recheck":("WEEKLY",30,"Re-evaluate WATCH/INVESTIGATE records"),
 "buyer_match":("DAILY",15,"Re-run active buyer requirements against opportunity universe"),
 "outcome_rollup":("DAILY",40,"Refresh qualified seller/appointment/listing/closing scoreboard")
}
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    for k,(cad,p,n) in POLICY.items():
        c.execute("""insert into source_schedule(source_key,cadence,priority,notes) values(?,?,?,?)
          on conflict(source_key) do update set cadence=excluded.cadence,priority=excluded.priority,notes=excluded.notes""",(k,cad,p,n))
    c.commit()
    for r in c.execute("select source_key,cadence,enabled,priority from source_schedule order by priority"): print(r)
    c.close()
if __name__=="__main__": main()
