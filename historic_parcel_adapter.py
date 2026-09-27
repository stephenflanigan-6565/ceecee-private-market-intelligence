#!/usr/bin/env python3
"""Historic-parcel lineage adapter. Preserves retired/changed parcel states as property memory."""
from db import connect
import json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"
URL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelHistoricPolygon/FeatureServer/0/query"
def utc(): return datetime.now(timezone.utc).isoformat()
def get(params):
    with urllib.request.urlopen(urllib.request.Request(URL+"?"+urllib.parse.urlencode(params),
        headers={"User-Agent":"CEECEE-PMI/5.0"}),timeout=90) as r: x=json.load(r)
    if "error" in x: raise RuntimeError(x["error"])
    return x
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    for pid in [r[0] for r in c.execute("select parcel_id from properties")]:
        safe=pid.replace("'","''")
        x=get({"where":f"PARCELID = '{safe}'","outFields":"PARCELID,FULLADDRESS,ACREAGE,FRONTAGE,DEPTH,LANDUSE,LASTUPDATE,CREATEDATE,STATUS","returnGeometry":"false","f":"json"})
        for feat in x.get("features",[]):
            a=feat["attributes"]
            c.execute("""insert or ignore into parcel_lineage(parcel_id,status,full_address,acreage,frontage,depth,land_use,
              source_created_at,source_last_update,observed_at,source) values(?,?,?,?,?,?,?,?,?,?,?)""",
              (pid,a.get("STATUS"),a.get("FULLADDRESS"),a.get("ACREAGE"),a.get("FRONTAGE"),a.get("DEPTH"),a.get("LANDUSE"),
               str(a.get("CREATEDATE")),str(a.get("LASTUPDATE")),utc(),"Suffolk TaxParcelHistoricPolygon"))
    c.commit(); c.close()
if __name__=="__main__": main()
