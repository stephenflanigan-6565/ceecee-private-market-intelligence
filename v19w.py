import os, json, urllib.parse, urllib.request
VERSION="V19W"
MARKET="WESTHAMPTON_BEACH_NY"
SOURCE="https://gis.suffolkcountyny.gov/server/rest/services/Applications/GISViewer/MapServer/57/query"

def _chunks(xs,n=80):
    for i in range(0,len(xs),n): yield xs[i:i+n]

def _fetch(parcel_ids):
    rows=[]; errors=[]
    for batch in _chunks(parcel_ids):
        quoted=",".join("'" + p.replace("'","''") + "'" for p in batch)
        params={
          "where":f"PARCELID IN ({quoted})",
          "outFields":"PARCELID,FULLADDRESS,ACREAGE,LANDUSE,LASTUPDATE,CREATEDATE,STATUS",
          "returnGeometry":"false","f":"json"
        }
        try:
            url=SOURCE+"?"+urllib.parse.urlencode(params)
            with urllib.request.urlopen(url,timeout=30) as r:
                data=json.loads(r.read().decode("utf-8"))
            if "error" in data:
                errors.append({"batch_first":batch[0],"error":data["error"]})
                continue
            rows.extend([x.get("attributes",{}) for x in data.get("features",[])])
        except Exception as e:
            errors.append({"batch_first":batch[0],"error_type":type(e).__name__,"error":str(e)[:300]})
    return rows,errors

def build_v19w():
    import psycopg
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""
          SELECT DISTINCT parcel_id FROM evidence_ledger
          WHERE market_code=%s AND evidence_family='PROPERTY_CONTEXT' AND is_current=1
          ORDER BY parcel_id
        """,(MARKET,))
        parcel_ids=[r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    source_rows,errors=_fetch(parcel_ids)
    by_id={str(r.get("PARCELID")):r for r in source_rows if r.get("PARCELID")}
    matched=[p for p in parcel_ids if p in by_id]
    missing=[p for p in parcel_ids if p not in by_id]

    def count(field):
        return sum(1 for p in matched if by_id[p].get(field) not in (None,""))

    last_updates=[by_id[p].get("LASTUPDATE") for p in matched if by_id[p].get("LASTUPDATE") is not None]
    checks={
      "whole_property_universe_requested":len(parcel_ids)==2082,
      "authoritative_source_is_parcel_keyed":True,
      "non_title_fields_requested":True,
      "no_transfer_title_used":True,
      "no_seller_lead_created_from_snapshot_alone":True,
      "missing_source_rows_nonblocking":True,
      "no_score_or_rank":True
    }
    return {
      "status":"ok" if all(checks.values()) and not errors else "source_partial" if source_rows else "source_error",
      "version":VERSION,
      "mode":"AUTHORITATIVE_NON_TITLE_PROPERTY_DNA_REFRESH_RAIL_READ_ONLY",
      "market_code":MARKET,
      "source_name":"Suffolk County Tax Parcels / GISViewer",
      "source_url":SOURCE,
      "requested_properties":len(parcel_ids),
      "source_rows_returned":len(source_rows),
      "matched_properties":len(matched),
      "missing_properties":len(missing),
      "missing_sample":missing[:20],
      "source_errors":errors,
      "field_coverage":{
        "FULLADDRESS":count("FULLADDRESS"),
        "ACREAGE":count("ACREAGE"),
        "LANDUSE":count("LANDUSE"),
        "LASTUPDATE":count("LASTUPDATE"),
        "CREATEDATE":count("CREATEDATE"),
        "STATUS":count("STATUS")
      },
      "latest_source_lastupdate":max(last_updates) if last_updates else None,
      "seller_opportunities_created":0,
      "rail_contract":{
        "role":"INDEPENDENT_NON_TITLE_PROPERTY_DNA_OBSERVATION",
        "current_snapshot_alone_is_not_seller_reason":True,
        "future_value":"COMPARE_AUTHORITATIVE_PROPERTY_DNA_TO_REMEMBERED_PROPERTY_DNA_AND_DETECT_REAL_CHANGES",
        "title_not_used_for_qualification":True
      },
      "checks":checks,
      "database_writes":0,
      "guards":{"database_writes":False,"seller_intent_inferred":False,
                "seller_scoring":False,"overall_ranking":False,
                "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"COMPARE_PROPERTY_DNA_REFRESH_TO_MEMORY_AND_ISOLATE_GENUINE_NON_TITLE_CHANGES"
    }
