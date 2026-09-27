#!/usr/bin/env python3
"""Westhampton Beach canonical parcel-universe probe.

V15A is intentionally READ ONLY. It validates the official Suffolk County
TaxParcelPolygon feed and the proposed Westhampton Beach district filter before
any parcel is written to PostgreSQL.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PARCEL_URL = "https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"
WESTHAMPTON_DISTRICT = "0905"
WHERE = "DISTRICT = '0905' AND STATUS = 'A'"
FIELDS = "OBJECTID,PARCELID,DISTRICT,SECTION,BLOCK,LOT,MUNICIPALITY,ZIPCODE,FULLADDRESS,ACREAGE,FRONTAGE,DEPTH,LANDUSE,TITLEFLAG,STATUS,ACREDEED,CREATEDATE,LASTUPDATE"
PAGE_SIZE = 2000


def utc():
    return datetime.now(timezone.utc).isoformat()


def _fetch(params):
    url = PARCEL_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Private-Market-Intelligence/15A"})
    with urllib.request.urlopen(req, timeout=90) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def _pages():
    offset = 0
    while True:
        payload = _fetch({
            "where": WHERE,
            "outFields": FIELDS,
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "orderByFields": "OBJECTID",
            "f": "json",
        })
        features = payload.get("features", [])
        for feature in features:
            yield feature.get("attributes", {})
        if len(features) < PAGE_SIZE:
            break
        offset += len(features)


def probe():
    """Fetch and validate the candidate universe without touching the database."""
    fetched = 0
    missing_parcel_id = 0
    wrong_district = 0
    wrong_status = 0
    duplicate_parcel_ids = 0
    parcel_ids = set()
    samples = []

    for row in _pages():
        fetched += 1
        parcel_id = row.get("PARCELID")
        if not parcel_id:
            missing_parcel_id += 1
            continue
        if str(row.get("DISTRICT") or "").strip() != WESTHAMPTON_DISTRICT:
            wrong_district += 1
        if str(row.get("STATUS") or "").strip() != "A":
            wrong_status += 1
        if parcel_id in parcel_ids:
            duplicate_parcel_ids += 1
        else:
            parcel_ids.add(parcel_id)
        if len(samples) < 5:
            samples.append({
                "parcel_id": parcel_id,
                "district": row.get("DISTRICT"),
                "municipality": row.get("MUNICIPALITY"),
                "address": row.get("FULLADDRESS"),
                "status": row.get("STATUS"),
            })

    valid = (
        fetched > 0
        and missing_parcel_id == 0
        and wrong_district == 0
        and wrong_status == 0
        and duplicate_parcel_ids == 0
        and len(parcel_ids) == fetched
    )
    return {
        "status": "ok" if valid else "validation_failed",
        "mode": "READ_ONLY_PROBE",
        "source": "Suffolk County TaxParcelPolygon",
        "source_url": PARCEL_URL.rsplit("/query", 1)[0],
        "where": WHERE,
        "generated_at": utc(),
        "records_fetched": fetched,
        "unique_parcel_ids": len(parcel_ids),
        "missing_parcel_id": missing_parcel_id,
        "wrong_district": wrong_district,
        "wrong_status": wrong_status,
        "duplicate_parcel_ids": duplicate_parcel_ids,
        "database_writes": 0,
        "property_data_touched": False,
        "outreach_touched": False,
        "samples": samples,
    }
