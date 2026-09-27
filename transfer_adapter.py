#!/usr/bin/env python3
"""Official Suffolk transfer-history adapter for parcels already admitted to CEECEE property memory."""
from db import connect, insert_id, insert_cursor
import json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/"ceecee.db"
CURRENT="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferCurrent/FeatureServer/0/query"
HISTORY="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/FeatureServer/0/query"

def utc(): return datetime.now(timezone.utc).isoformat()
def fetch(url, params):
    u=url+"?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"CEECEE-PMI/3.0"}),timeout=90) as r:
        x=json.load(r)
    if "error" in x: raise RuntimeError(x["error"])
    return x
def q(url,pid,fields):
    x=fetch(url,{"where":f"PARCELID = '{pid.replace(chr(39), chr(39)*2)}'","outFields":fields,
                 "returnGeometry":"false","orderByFields":"TRANSHISSEQ","f":"json"})
    return [f["attributes"] for f in x.get("features",[])]
def put(c,pid,a,source):
    ts=utc()
    vals=(pid,a.get("TRANSHISSEQ"),a.get("LIBERPAGE"),str(a.get("RECORDDATE")),a.get("DOCNUM"),
          a.get("DOCCODE"),str(a.get("DOCDATE")),str(a.get("ENTRYDATE")),str(a.get("SALEDATE")),
          a.get("SALEPRICE"),source,ts)
    before=c.total_changes
    c.execute("""INSERT OR IGNORE INTO transfers(parcel_id,history_sequence,liber_page,record_date,document_number,
      document_code,document_date,entry_date,sale_date,sale_price,source,observed_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",vals)
    if c.total_changes>before:
        eid=insert_cursor(c,"""INSERT INTO events(parcel_id,event_type,event_date,observed_at,source,evidence_grade,details_json)
          VALUES(?,?,?,?,?,?,?)""",(pid,"RECORDED_TRANSFER_EVENT",str(a.get("RECORDDATE") or a.get("SALEDATE")),ts,
          source,"A",json.dumps(a,sort_keys=True,default=str)))
        c.execute("""INSERT OR IGNORE INTO signals(parcel_id,signal_type,observed_at,source_event_id,confidence)
          VALUES(?,?,?,?,?)""",(pid,"RECORDED_TRANSFER_ACTIVITY",ts,eid,"HIGH"))
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    pids=[r[0] for r in c.execute("select parcel_id from properties")]
    for pid in pids:
        for a in q(HISTORY,pid,"PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ"):
            put(c,pid,a,"Suffolk TaxParcelTransferHistory")
        for a in q(CURRENT,pid,"PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ,SALEDATE,SALEPRICE"):
            put(c,pid,a,"Suffolk TaxParcelTransferCurrent")
    c.commit()
    print({"pilot_parcels":len(pids),"transfer_records":c.execute("select count(*) from transfers").fetchone()[0]})
    c.close()
if __name__=="__main__": main()
