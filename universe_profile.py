#!/usr/bin/env python3
"""V15C read-only profile of the locked Westhampton Beach canonical universe.

Purpose: learn the actual composition/completeness of the 2,545 canonical parcels
before inventing residential classifications. PostgreSQL reads only.
No property writes, scoring, opportunities, relationship data, or outreach.
"""
from datetime import datetime, timezone
from db import connect, execute, backend

DISTRICT = "0905"


def utc():
    return datetime.now(timezone.utc).isoformat()


def _rows(cur):
    return cur.fetchall()


def profile():
    c = connect()
    try:
        total = execute(c, "SELECT COUNT(*) FROM properties WHERE district=? AND status='A'", (DISTRICT,)).fetchone()[0]
        land_rows = _rows(execute(c, """
            SELECT COALESCE(NULLIF(TRIM(land_use),''),'(missing)') AS land_use, COUNT(*) AS n
            FROM properties WHERE district=? AND status='A'
            GROUP BY COALESCE(NULLIF(TRIM(land_use),''),'(missing)')
            ORDER BY n DESC, land_use ASC
        """, (DISTRICT,)))
        municipality_rows = _rows(execute(c, """
            SELECT COALESCE(NULLIF(TRIM(municipality),''),'(missing)') AS municipality, COUNT(*) AS n
            FROM properties WHERE district=? AND status='A'
            GROUP BY COALESCE(NULLIF(TRIM(municipality),''),'(missing)')
            ORDER BY n DESC, municipality ASC
        """, (DISTRICT,)))
        completeness = execute(c, """
            SELECT
              SUM(CASE WHEN full_address IS NULL OR TRIM(full_address)='' THEN 1 ELSE 0 END),
              SUM(CASE WHEN land_use IS NULL OR TRIM(land_use)='' THEN 1 ELSE 0 END),
              SUM(CASE WHEN acreage IS NULL THEN 1 ELSE 0 END),
              SUM(CASE WHEN section IS NULL OR TRIM(section)='' THEN 1 ELSE 0 END),
              SUM(CASE WHEN block IS NULL OR TRIM(block)='' THEN 1 ELSE 0 END),
              SUM(CASE WHEN lot IS NULL OR TRIM(lot)='' THEN 1 ELSE 0 END)
            FROM properties WHERE district=? AND status='A'
        """, (DISTRICT,)).fetchone()
        samples = _rows(execute(c, """
            SELECT parcel_id, full_address, land_use, acreage
            FROM properties WHERE district=? AND status='A'
            ORDER BY parcel_id LIMIT 10
        """, (DISTRICT,)))
        return {
            "status":"ok",
            "mode":"READ_ONLY_UNIVERSE_PROFILE",
            "database_backend":backend(),
            "generated_at":utc(),
            "district":DISTRICT,
            "canonical_active_parcels":total,
            "land_use_distribution":[{"land_use":str(r[0]),"count":int(r[1])} for r in land_rows],
            "municipality_distribution":[{"municipality":str(r[0]),"count":int(r[1])} for r in municipality_rows],
            "completeness":{
                "missing_address":int(completeness[0] or 0),
                "missing_land_use":int(completeness[1] or 0),
                "missing_acreage":int(completeness[2] or 0),
                "missing_section":int(completeness[3] or 0),
                "missing_block":int(completeness[4] or 0),
                "missing_lot":int(completeness[5] or 0),
            },
            "samples":[{"parcel_id":r[0],"address":r[1],"land_use":r[2],"acreage":r[3]} for r in samples],
            "database_writes":0,
            "property_data_touched":False,
            "opportunity_data_touched":False,
            "outreach_touched":False,
            "classification_applied":False,
        }
    finally:
        c.close()
