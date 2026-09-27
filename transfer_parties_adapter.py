#!/usr/bin/env python3
"""Backfill official grantor/grantee parties for transfer history already stored."""
from db import connect
import json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"ceecee.db"
BASE="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData"
URLS={
 "GRANTOR":BASE+"/TaxParcelGrantor/FeatureServer/0/query",
 "GRANTEE":BASE+"/TaxParcelGrantee/FeatureServer/0/query"
}
def utc(): return datetime.now(timezone.utc).isoformat()
def fetch(url,params):
    with urllib.request.urlopen(urllib.request.Request(url+"?"+urllib.parse.urlencode(params),
         headers={"User-Agent":"CEECEE-PMI/4.0"}),timeout=90) as r: x=json.load(r)
    if "error" in x: raise RuntimeError(x["error"])
    return x
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    for pid in [x[0] for x in c.execute("select parcel_id from properties")]:
        safe=pid.replace("'","''")
        for role,url in URLS.items():
            x=fetch(url,{"where":f"PARCELID = '{safe}'",
              "outFields":"PARCELID,TRANSHISSEQ,FIRSTNAME,LASTNAME,MIDDLEINITIAL,SUFFIXNAME,OWNPERCENT,OWNERTYPE,BUSSINESS",
              "returnGeometry":"false","f":"json"})
            for feat in x.get("features",[]):
                a=feat["attributes"]
                c.execute("""insert or ignore into transfer_parties(parcel_id,history_sequence,role,first_name,last_name,
                  middle_initial,suffix,ownership_percent,owner_type,business_flag,source,observed_at)
                  values(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (pid,a.get("TRANSHISSEQ"),role,a.get("FIRSTNAME"),a.get("LASTNAME"),a.get("MIDDLEINITIAL"),
                   a.get("SUFFIXNAME"),a.get("OWNPERCENT"),a.get("OWNERTYPE"),a.get("BUSSINESS"),
                   "Suffolk TaxParcel"+role.title(),utc()))
    c.commit()
    print({"transfer_parties":c.execute("select count(*) from transfer_parties").fetchone()[0]})
    c.close()
if __name__=="__main__": main()
