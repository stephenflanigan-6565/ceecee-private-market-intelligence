#!/usr/bin/env python3
"""Building-footprint enrichment by spatial intersection; context only, never seller intent."""
from db import connect
import json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/"ceecee.db"
PARCEL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"
BLDG="https://gis.southamptontownny.gov/gisserver/rest/services/DataServices/ePortal/MapServer/22/query"
def utc(): return datetime.now(timezone.utc).isoformat()
def get(url,p):
    with urllib.request.urlopen(urllib.request.Request(url+"?"+urllib.parse.urlencode(p),headers={"User-Agent":"CEECEE-PMI/5.0"}),timeout=90) as r:x=json.load(r)
    if "error" in x: raise RuntimeError(x["error"])
    return x
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    for pid in [r[0] for r in c.execute("select parcel_id from properties")]:
        safe=pid.replace("'","''")
        px=get(PARCEL,{"where":f"PARCELID = '{safe}'","outFields":"PARCELID","returnGeometry":"true","outSR":"2263","f":"json"})
        fs=px.get("features",[])
        if not fs or not fs[0].get("geometry"): continue
        geom=fs[0]["geometry"]
        q=get(BLDG,{"geometry":json.dumps(geom),"geometryType":"esriGeometryPolygon","inSR":"2263",
                    "spatialRel":"esriSpatialRelIntersects","outFields":"BLDG_ID,Bldg_Count,Shape_Area,PERIMETER",
                    "returnGeometry":"false","f":"json"})
        attrs=[x["attributes"] for x in q.get("features",[])]
        c.execute("""insert into building_context(parcel_id,building_count,footprint_area,footprint_perimeter,observed_at,source)
          values(?,?,?,?,?,?) on conflict(parcel_id) do update set building_count=excluded.building_count,
          footprint_area=excluded.footprint_area,footprint_perimeter=excluded.footprint_perimeter,
          observed_at=excluded.observed_at,source=excluded.source""",
          (pid,len(attrs),sum((a.get("Shape_Area") or 0) for a in attrs),sum((a.get("PERIMETER") or 0) for a in attrs),
           utc(),"Southampton ePortal Building Footprints"))
    c.commit(); c.close()
if __name__=="__main__": main()
