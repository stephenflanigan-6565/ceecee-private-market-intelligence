#!/usr/bin/env python3
"""
from db import connect
Location enrichment rail.
Uses parcel geometry against Southampton's Westhampton Beach zoning layer.
The spatial join is intentionally performed by geometry, not by assuming a shared parcel-id format.
"""
import json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"ceecee.db"
PARCEL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"
ZONING="https://gis.southamptontownny.gov/gisserver/rest/services/DataServices/LandManager/MapServer/41/query"
def utc(): return datetime.now(timezone.utc).isoformat()
def get(url,p):
    with urllib.request.urlopen(urllib.request.Request(url+"?"+urllib.parse.urlencode(p),
        headers={"User-Agent":"CEECEE-PMI/4.0"}),timeout=90) as r: x=json.load(r)
    if "error" in x: raise RuntimeError(x["error"])
    return x
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    for pid in [x[0] for x in c.execute("select parcel_id from properties")]:
        safe=pid.replace("'","''")
        px=get(PARCEL,{"where":f"PARCELID = '{safe}'","outFields":"PARCELID","returnGeometry":"true",
                       "outSR":"4326","f":"json"})
        fs=px.get("features",[])
        if not fs: continue
        geom=fs[0].get("geometry")
        if not geom: continue
        # Use polygon envelope for candidate zoning lookup; production validation can test exact intersection.
        rings=geom.get("rings",[])
        pts=[p for ring in rings for p in ring]
        if not pts: continue
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        env={"xmin":min(xs),"ymin":min(ys),"xmax":max(xs),"ymax":max(ys),"spatialReference":{"wkid":4326}}
        z=get(ZONING,{"geometry":json.dumps(env),"geometryType":"esriGeometryEnvelope","inSR":"4326",
                      "spatialRel":"esriSpatialRelIntersects","outFields":"CODE,ZONE,DESCRIPT,DIM_REG",
                      "returnGeometry":"false","f":"json"})
        attrs=(z.get("features") or [{}])[0].get("attributes",{})
        c.execute("""insert into property_context(parcel_id,zoning_code,zoning_name,zoning_description,
          zoning_dimensional_regulation,building_footprint_present,context_observed_at,context_source)
          values(?,?,?,?,?,?,?,?) on conflict(parcel_id) do update set zoning_code=excluded.zoning_code,
          zoning_name=excluded.zoning_name,zoning_description=excluded.zoning_description,
          zoning_dimensional_regulation=excluded.zoning_dimensional_regulation,
          context_observed_at=excluded.context_observed_at,context_source=excluded.context_source""",
          (pid,attrs.get("CODE"),attrs.get("ZONE"),attrs.get("DESCRIPT"),attrs.get("DIM_REG"),None,utc(),
           "Southampton LandManager Westhampton Beach zoning"))
    c.commit(); c.close()
if __name__=="__main__": main()
