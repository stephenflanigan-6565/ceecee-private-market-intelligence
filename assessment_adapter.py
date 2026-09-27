#!/usr/bin/env python3
"""
from db import connect
Normalize annual Westhampton Beach assessment exports into persistent history.
Input CSV columns:
parcel_id,roll_year,assessed_land,assessed_total,market_value,acreage,property_class,source
This adapter deliberately separates assessment value from market estimates/AVMs.
"""
import argparse,csv,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"
def utc(): return datetime.now(timezone.utc).isoformat()
def num(x):
    if x is None or str(x).strip()=="": return None
    return float(str(x).replace("$","").replace(",","").strip())
def main(path):
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    with open(path,newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            c.execute("""insert into assessment_history(parcel_id,roll_year,assessed_land,assessed_total,market_value,acreage,property_class,source,observed_at)
              values(?,?,?,?,?,?,?,?,?) on conflict(parcel_id,roll_year,source) do update set
              assessed_land=excluded.assessed_land,assessed_total=excluded.assessed_total,market_value=excluded.market_value,
              acreage=excluded.acreage,property_class=excluded.property_class,observed_at=excluded.observed_at""",
              (r["parcel_id"],int(r["roll_year"]),num(r.get("assessed_land")),num(r.get("assessed_total")),
               num(r.get("market_value")),num(r.get("acreage")),r.get("property_class"),r.get("source") or "Southampton official assessment roll",utc()))
    c.commit(); c.close()
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("csv"); a=ap.parse_args(); main(a.csv)
