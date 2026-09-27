#!/usr/bin/env python3
"""V15K2 — NYS ORPTS assessment/value source probe.

READ ONLY. Replaces the rejected live Southampton-PDF transport path with the
public NYS Tax Parcels Feature Service, whose attributes are populated from
ORPTS local assessment-roll data. V15K2 measures coverage/join quality only.
No assessment rows are persisted.
"""
import json, re, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from db import connect, execute, backend

VERSION="V15K3"
MODE="READ_ONLY_NYS_ORPTS_ASSESSMENT_VALUE_SOURCE_PROBE_CANONICAL_KEY_REPAIR"
DISTRICT="0905"
SWIS="473607"
EXPECTED_CANONICAL=2545
SOURCE="NYS ITS Tax Parcels Public / ORPTS assessment-roll attributes"
SERVICE="https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Tax_Parcels_Public/FeatureServer/1/query"
OUT_FIELDS="OBJECTID,SWIS,SBL,PRINT_KEY,PROP_CLASS,LAND_AV,TOTAL_AV,FULL_MARKET_VAL,YR_BLT,ACRES,ROLL_YR,PARCEL_ADDR,SQFT_LIVING,NBR_FULL_BATHS,NBR_BEDROOMS,BLDG_STYLE_DESC,USED_AS_DESC"

def utc(): return datetime.now(timezone.utc).isoformat()

def norm_component(value):
    s=str(value or "").strip()
    if not s: return None
    try:
        d=Decimal(s)
        if d==d.to_integral(): return str(d.quantize(Decimal(1)))
        return format(d.normalize(),"f")
    except InvalidOperation:
        s="".join(ch for ch in s if ch.isdigit() or ch==".")
        if not s: return None
        try:
            d=Decimal(s)
            if d==d.to_integral(): return str(d.quantize(Decimal(1)))
            return format(d.normalize(),"f")
        except InvalidOperation: return None

def key(section,block,lot): return (norm_component(section),norm_component(block),norm_component(lot))

def canonical_component(value, scale):
    """Decode Suffolk fixed-width canonical S/B/L storage to ORPTS print-key units.

    Canonical examples observed in V15K2:
      section 00100 -> 1
      block   01000 -> 1
      lot     01001 -> 1.001
    """
    s=str(value or "").strip()
    if not s: return None
    try:
        return norm_component(Decimal(s) / Decimal(scale))
    except InvalidOperation:
        return None

def canonical_key(section,block,lot):
    return (canonical_component(section,100),
            canonical_component(block,1000),
            canonical_component(lot,1000))

def key_from_sbl(value):
    s=str(value or "").strip()
    # ORPTS/Suffolk form commonly: 012.000-0001-013.000
    m=re.search(r"(\d{1,3}(?:\.\d+)?)\s*-\s*(\d{1,4}(?:\.\d+)?)\s*-\s*(\d{1,3}(?:\.\d+)?)",s)
    if not m: return None
    return key(*m.groups())

def _fetch_page(offset, page_size=2000):
    params={
      "where":f"SWIS='{SWIS}'", "outFields":OUT_FIELDS, "returnGeometry":"false",
      "resultOffset":str(offset), "resultRecordCount":str(page_size), "orderByFields":"OBJECTID",
      "f":"json"
    }
    url=SERVICE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"Private-Market-Intelligence/V15K2"})
    with urllib.request.urlopen(req,timeout=30) as r:
        payload=json.loads(r.read().decode("utf-8"))
    if "error" in payload: raise RuntimeError(f"NYS ArcGIS error: {payload['error']}")
    return payload

def fetch_state_rows():
    features=[]; offset=0; pages=0
    while True:
        payload=_fetch_page(offset); pages+=1
        batch=payload.get("features") or []
        features.extend((f.get("attributes") or {}) for f in batch)
        if not payload.get("exceededTransferLimit") and len(batch)<2000: break
        if not batch: break
        offset += len(batch)
        if pages>10: raise RuntimeError("NYS assessment pagination guard exceeded")
    return pages,features

def probe_assessment_v15k():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id,section,block,lot FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchall()
    finally: c.close()
    if len(rows)!=EXPECTED_CANONICAL:
        raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {len(rows)}")

    canonical={}
    for r in rows: canonical.setdefault(canonical_key(r[1],r[2],r[3]),[]).append(str(r[0]))
    canonical_collisions={k:v for k,v in canonical.items() if None not in k and len(v)>1}

    pages,state_rows=fetch_state_rows()
    parsed=[]; unparsable=[]
    for a in state_rows:
        k=key_from_sbl(a.get("SBL")) or key_from_sbl(a.get("PRINT_KEY"))
        if k is None: unparsable.append(a.get("SBL") or a.get("PRINT_KEY"))
        else: parsed.append((k,a))
    counts=Counter(k for k,_ in parsed)
    state_keys=set(counts)
    matched=state_keys & set(canonical)
    unmatched_state=sorted(state_keys-set(canonical))
    unmatched_canonical=sorted(set(canonical)-state_keys)
    matched_parcels=sum(len(canonical[k]) for k in matched)

    def present(field): return sum(1 for _,a in parsed if a.get(field) not in (None,""))
    roll_years=sorted({a.get("ROLL_YR") for _,a in parsed if a.get("ROLL_YR") is not None})
    return {
      "status":"ok","version":VERSION,"mode":MODE,"database_backend":backend(),
      "source":SOURCE,"source_service":SERVICE.rsplit('/query',1)[0],"swis":SWIS,"district":DISTRICT,
      "generated_at":utc(),"measurement_only":True,"pages":pages,"records_fetched":len(state_rows),
      "roll_years_present":roll_years,"unique_state_taxmaps":len(state_keys),
      "unparsable_state_taxmaps":len(unparsable),"duplicate_state_taxmap_records":sum(n-1 for n in counts.values() if n>1),
      "canonical_active_parcels":len(rows),"canonical_unique_normalized_keys":len(canonical),
      "canonical_normalization_collisions":len(canonical_collisions),
      "matched_unique_state_taxmaps":len(matched),"matched_canonical_parcels":matched_parcels,
      "canonical_match_pct":round(100*matched_parcels/len(rows),2) if rows else 0,
      "unmatched_state_taxmaps":len(unmatched_state),
      "unmatched_canonical_parcels":sum(len(canonical[k]) for k in unmatched_canonical),
      "field_coverage":{
        "property_class":present("PROP_CLASS"),"acreage":present("ACRES"),"assessed_land":present("LAND_AV"),
        "assessed_total":present("TOTAL_AV"),"full_market_value":present("FULL_MARKET_VAL"),"year_built":present("YR_BLT"),
        "living_sqft":present("SQFT_LIVING"),"bedrooms":present("NBR_BEDROOMS"),"full_baths":present("NBR_FULL_BATHS")
      },
      "sample_unmatched_state":["-".join(x for x in k if x is not None) for k in unmatched_state[:10]],
      "sample_unmatched_canonical":[{"normalized_taxmap":"-".join(x for x in k if x is not None),"parcel_ids":canonical[k][:3]} for k in unmatched_canonical[:10]],
      "important_scope_note":"V15K3 repairs only the canonical Suffolk fixed-width S/B/L normalization discovered by V15K2. NYS public service currently exposes 2025 ORPTS assessment-roll attributes; 2026 Southampton roll remains a later annual-snapshot enrichment, not a blocker.",
      "database_writes":0,"assessment_data_touched":False,"seller_scoring_touched":False,
      "opportunity_data_touched":False,"outreach_touched":False
    }
