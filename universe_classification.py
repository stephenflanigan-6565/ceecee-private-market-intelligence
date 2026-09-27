#!/usr/bin/env python3
"""V15D Westhampton factual property-use cohort preview.

Read-only. Derives a coarse cohort from the raw official NY/Suffolk LANDUSE
code already stored in canonical property memory. It does not score seller
intent, create opportunities, modify property rows, or touch outreach.

The raw LANDUSE code remains authoritative source evidence. This module adds
only a reversible research interpretation for universe segmentation.
"""
from datetime import datetime, timezone
from db import connect, execute, backend

DISTRICT = "0905"

# NYS ORPTS property-class structure. These are intentionally broad factual
# use cohorts, not seller/opportunity scores.
RESIDENTIAL_VACANT_CODES = {"310", "311", "312", "314", "315", "320", "321", "322", "323"}
COMMERCIAL_VACANT_CODES = {"330", "331"}
INDUSTRIAL_VACANT_CODES = {"340", "341"}
PUBLIC_UTILITY_VACANT_CODES = {"380"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def classify_land_use(code):
    if code is None or str(code).strip() == "":
        return "UNRESOLVED"
    code = str(code).strip()
    if code.startswith("2"):
        return "RESIDENTIAL_IMPROVED"
    if code in RESIDENTIAL_VACANT_CODES:
        return "RESIDENTIAL_VACANT_LAND"
    if code in COMMERCIAL_VACANT_CODES or code.startswith("4"):
        return "COMMERCIAL_MIXED"
    if code in PUBLIC_UTILITY_VACANT_CODES or code.startswith("6") or code.startswith("8"):
        return "COMMUNITY_PUBLIC_UTILITY"
    if code in INDUSTRIAL_VACANT_CODES or code.startswith("5") or code.startswith("7") or code.startswith("9"):
        return "OTHER_NON_TARGET"
    # Any 3xx code not explicitly mapped above remains unresolved rather than
    # being silently forced into a business category.
    return "UNRESOLVED"


def preview():
    c = connect()
    try:
        rows = execute(c, """SELECT parcel_id, full_address, land_use, acreage
                             FROM properties
                             WHERE district=? AND status='A'
                             ORDER BY parcel_id""", (DISTRICT,)).fetchall()
        counts = {}
        by_code = {}
        samples = {}
        for row in rows:
            pid, address, land_use, acreage = tuple(row)
            cohort = classify_land_use(land_use)
            counts[cohort] = counts.get(cohort, 0) + 1
            raw = str(land_use).strip() if land_use is not None and str(land_use).strip() else "(missing)"
            by_code[(cohort, raw)] = by_code.get((cohort, raw), 0) + 1
            if len(samples.setdefault(cohort, [])) < 5:
                samples[cohort].append({"parcel_id": pid, "address": address,
                                        "land_use": land_use, "acreage": acreage})

        cohort_order = ["RESIDENTIAL_IMPROVED", "RESIDENTIAL_VACANT_LAND",
                        "COMMERCIAL_MIXED", "COMMUNITY_PUBLIC_UTILITY",
                        "OTHER_NON_TARGET", "UNRESOLVED"]
        return {
            "status": "ok",
            "mode": "READ_ONLY_CLASSIFICATION_PREVIEW",
            "database_backend": backend(),
            "district": DISTRICT,
            "canonical_active_parcels": len(rows),
            "classification_applied": False,
            "cohort_counts": [{"cohort": k, "count": counts.get(k, 0)} for k in cohort_order],
            "cohort_total": sum(counts.values()),
            "code_breakdown": [
                {"cohort": cohort, "land_use": code, "count": count}
                for (cohort, code), count in sorted(by_code.items(), key=lambda x: (x[0][0], -x[1], x[0][1]))
            ],
            "samples": samples,
            "database_writes": 0,
            "property_data_touched": False,
            "opportunity_data_touched": False,
            "outreach_touched": False,
            "generated_at": utc(),
        }
    finally:
        c.close()
