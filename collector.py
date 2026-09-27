#!/usr/bin/env python3
from db import connect, insert_id, insert_cursor
import argparse, hashlib, json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/"ceecee.db"
PARCEL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"
OWNER="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelOwner/FeatureServer/0/query"

def utc(): return datetime.now(timezone.utc).isoformat()
def h(x): return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
def db():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text()); return c
def fetch(url,params):
    u=url+"?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"CEECEE-PMI/2.0"}),timeout=90) as r:
        x=json.load(r)
    if "error" in x: raise RuntimeError(x["error"])
    return x
def pages(url,where,fields):
    off=0
    while True:
        x=fetch(url,{"where":where,"outFields":fields,"returnGeometry":"false",
                     "resultOffset":off,"resultRecordCount":2000,"orderByFields":"OBJECTID","f":"json"})
        fs=x.get("features",[])
        for f in fs: yield f["attributes"]
        if len(fs)<2000: break
        off+=len(fs)
def snap(c,pid,source,payload):
    ts=utc(); ph=h(payload)
    old=c.execute("select payload_json from snapshots where parcel_id=? and source=? order by id desc limit 1",(pid,source)).fetchone()
    changed=bool(old and h(json.loads(old[0]))!=ph)
    c.execute("insert or ignore into snapshots(parcel_id,source,observed_at,payload_json,payload_hash) values(?,?,?,?,?)",
              (pid,source,ts,json.dumps(payload,sort_keys=True),ph))
    return changed, (json.loads(old[0]) if old else None), ts
def parcel_record(a):
    return {k.lower():a.get(k) for k in ["PARCELID","DISTRICT","SECTION","BLOCK","LOT","MUNICIPALITY",
      "ZIPCODE","FULLADDRESS","ACREAGE","FRONTAGE","DEPTH","LANDUSE","TITLEFLAG","STATUS","ACREDEED","CREATEDATE","LASTUPDATE"]}
def run(where):
    c=db(); start=utc()
    rid=insert_cursor(c,"insert into source_runs(source,started_at,status) values(?,?,?)",("Suffolk parcel+owner",start,"RUNNING"))
    seen=changed=0
    try:
        for a in pages(PARCEL,where,"OBJECTID,PARCELID,DISTRICT,SECTION,BLOCK,LOT,MUNICIPALITY,ZIPCODE,FULLADDRESS,ACREAGE,FRONTAGE,DEPTH,LANDUSE,TITLEFLAG,STATUS,ACREDEED,CREATEDATE,LASTUPDATE"):
            r=parcel_record(a); pid=r["parcelid"]
            if not pid: continue
            seen+=1; ch,before,ts=snap(c,pid,"Suffolk TaxParcelPolygon",r); changed+=int(ch)
            c.execute("""insert into properties values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              on conflict(parcel_id) do update set district=excluded.district,section=excluded.section,block=excluded.block,
              lot=excluded.lot,municipality=excluded.municipality,zipcode=excluded.zipcode,full_address=excluded.full_address,
              acreage=excluded.acreage,frontage=excluded.frontage,depth=excluded.depth,land_use=excluded.land_use,
              title_flag=excluded.title_flag,status=excluded.status,deed_acreage=excluded.deed_acreage,
              source_created_at=excluded.source_created_at,source_last_update=excluded.source_last_update,last_seen_at=excluded.last_seen_at""",
              (pid,r["district"],r["section"],r["block"],r["lot"],r["municipality"],r["zipcode"],r["fulladdress"],
               r["acreage"],r["frontage"],r["depth"],r["landuse"],r["titleflag"],r["status"],r["acredeed"],
               str(r["createdate"]),str(r["lastupdate"]),ts,ts))
            if ch:
                diff={k:{"before":before.get(k),"after":r.get(k)} for k in r if before.get(k)!=r.get(k)}
                eid=insert_cursor(c,"insert into events(parcel_id,event_type,observed_at,source,evidence_grade,details_json) values(?,?,?,?,?,?)",
                  (pid,"PARCEL_STATE_CHANGED",ts,"Suffolk TaxParcelPolygon","A",json.dumps(diff)))
                c.execute("insert or ignore into signals(parcel_id,signal_type,observed_at,source_event_id) values(?,?,?,?)",
                          (pid,"PROPERTY_STATE_CHANGE",ts,eid))
        # Owner join only for parcels already admitted by the pilot filter.
        for a in pages(OWNER,"PARCELID IS NOT NULL","OBJECTID,PARCELID,FIRSTNAME,LASTNAME,OWNERNAME"):
            pid=a.get("PARCELID")
            if not pid or not c.execute("select 1 from properties where parcel_id=?",(pid,)).fetchone(): continue
            p={"parcelid":pid,"firstname":a.get("FIRSTNAME"),"lastname":a.get("LASTNAME"),"ownername":a.get("OWNERNAME")}
            ch,before,ts=snap(c,pid,"Suffolk TaxParcelOwner",p)
            c.execute("""insert into owners(parcel_id,owner_name,first_name,last_name,first_seen_at,last_seen_at)
              values(?,?,?,?,?,?) on conflict(parcel_id,owner_name,first_name,last_name) do update set last_seen_at=excluded.last_seen_at,active=1""",
              (pid,p["ownername"],p["firstname"],p["lastname"],ts,ts))
            if ch:
                eid=insert_cursor(c,"insert into events(parcel_id,event_type,observed_at,source,evidence_grade,details_json) values(?,?,?,?,?,?)",
                  (pid,"OWNER_RECORD_CHANGED",ts,"Suffolk TaxParcelOwner","A",json.dumps({"before":before,"after":p})))
                c.execute("insert or ignore into signals(parcel_id,signal_type,observed_at,source_event_id) values(?,?,?,?)",
                          (pid,"OWNER_RECORD_CHANGE",ts,eid))
        # Conservative triage: one independent signal type => WATCH; >=2 => INVESTIGATE. Never seller probability.
        for pid,n in c.execute("select parcel_id,count(distinct signal_type) from signals where active=1 group by parcel_id").fetchall():
            state="INVESTIGATE" if n>=2 else "WATCH"
            types=[x[0] for x in c.execute("select distinct signal_type from signals where parcel_id=? and active=1",(pid,))]
            why=" + ".join(types)
            c.execute("""insert into opportunities(parcel_id,state,why_now,independent_signal_types,updated_at) values(?,?,?,?,?)
              on conflict(parcel_id) do update set state=excluded.state,why_now=excluded.why_now,
              independent_signal_types=excluded.independent_signal_types,updated_at=excluded.updated_at""",(pid,state,why,n,utc()))
        c.execute("update source_runs set completed_at=?,records_seen=?,changed_records=?,status='OK' where id=?",(utc(),seen,changed,rid))
        c.commit()
    except Exception as e:
        c.execute("update source_runs set completed_at=?,records_seen=?,changed_records=?,status='ERROR',error=? where id=?",(utc(),seen,changed,str(e),rid)); c.commit(); raise
    finally: c.close()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--where",default="MUNICIPALITY = 'WESTHAMPTON BEACH'",
                    help="ArcGIS SQL predicate. Default is the Westhampton Beach municipality value; verify against live distinct values at deployment.")
    args=ap.parse_args(); run(args.where)
