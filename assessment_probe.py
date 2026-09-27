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

VERSION="V15K8"
MODE="READ_ONLY_ASSESSMENT_PARCEL_LINEAGE_RESIDUAL_DIAGNOSTIC"
DISTRICT="0905"
SWIS="473607"
EXPECTED_CANONICAL=2545
SOURCE="NYS ITS Tax Parcels Public / ORPTS assessment-roll attributes"
SERVICE="https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Tax_Parcels_Public/FeatureServer/1/query"
SUFFOLK_CURRENT="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"
SUFFOLK_HISTORIC="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelHistoricPolygon/FeatureServer/0/query"
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
      block   00100 -> 1
      lot     01001 -> 1.001
    """
    s=str(value or "").strip()
    if not s: return None
    try:
        return norm_component(Decimal(s) / Decimal(scale))
    except InvalidOperation:
        return None

def canonical_section_component(value):
    """Decode Suffolk section storage to ORPTS section notation.

    Live V15K4 evidence proved a Suffolk section such as 01101 maps to
    ORPTS 11.001 (not 11.01). The first two decimal-storage digits are a
    three-place ORPTS suffix. Whole sections remain unchanged: 00100 -> 1.
    """
    s=str(value or "").strip()
    if not s: return None
    try:
        n=int(Decimal(s))
    except (InvalidOperation, ValueError):
        return None
    whole=n//100
    suffix=n%100
    if suffix==0:
        return str(whole)
    return f"{whole}.{suffix:03d}"

def canonical_key(section,block,lot):
    return (canonical_section_component(section),
            canonical_component(block,100),
            canonical_component(lot,1000))

def key_from_sbl(value):
    s=str(value or "").strip()
    # Human-readable ORPTS/Suffolk form, e.g. 12.001-1-2.002.
    m=re.search(r"(\d{1,3}(?:\.\d+)?)\s*-\s*(\d{1,4}(?:\.\d+)?)\s*-\s*(\d{1,3}(?:\.\d+)?)",s)
    if m:
        return key(*m.groups())

    # V15K6 proved that the 75 previously-unparsable values are a second,
    # deterministic 20-digit Suffolk SBL encoding. Layout observed:
    #   SSSsss BBBB LLLLL EEEEE
    #   010000 0006 01900 00000 -> 10-6-19
    #   011000 0001 01000 10000 -> 11-1-10.001
    #   003001 0001 00500 00000 -> 3.001-1-5
    # Section = 3-digit whole + 3-digit suffix. Lot base is /100; the
    # extension encodes thousandths (10000 -> .001, 30000 -> .003).
    if re.fullmatch(r"\d{20}", s):
        sec_raw=s[0:6]; block_raw=s[6:10]; lot_raw=s[10:15]; ext_raw=s[15:20]
        sec_whole=int(sec_raw[:3]); sec_suffix=int(sec_raw[3:])
        section=str(sec_whole) if sec_suffix==0 else f"{sec_whole}.{sec_suffix:03d}"
        block=str(int(block_raw))
        lot_base=Decimal(int(lot_raw))/Decimal(100)
        lot_ext=Decimal(int(ext_raw))/Decimal(10000000)
        lot=norm_component(lot_base+lot_ext)
        return key(section,block,lot)
    return None

def _fetch_page(offset, page_size=2000):
    params={
      "where":f"SWIS='{SWIS}'", "outFields":OUT_FIELDS, "returnGeometry":"false",
      "resultOffset":str(offset), "resultRecordCount":str(page_size), "orderByFields":"OBJECTID",
      "f":"json"
    }
    url=SERVICE+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"Private-Market-Intelligence/V15K8"})
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

def _fetch_suffolk(service, where, out_fields):
    params={"where":where,"outFields":out_fields,"returnGeometry":"false","resultRecordCount":"2000","f":"json"}
    url=service+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"Private-Market-Intelligence/V15K8"})
    with urllib.request.urlopen(req,timeout=30) as r:
        payload=json.loads(r.read().decode("utf-8"))
    if "error" in payload: raise RuntimeError(f"Suffolk ArcGIS error: {payload['error']}")
    return [(f.get("attributes") or {}) for f in (payload.get("features") or [])]

def _epoch_iso(v):
    if v in (None,""): return None
    try: return datetime.fromtimestamp(float(v)/1000,timezone.utc).date().isoformat()
    except Exception: return None

def _suffolk_key(a):
    return canonical_key(a.get("SECTION"),a.get("BLOCK"),a.get("LOT"))

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

    # V15K8: classify only the residuals against Suffolk current/historic parcel facts.
    # No geometry inference and no forced parent/child match is made here.
    current_rows=_fetch_suffolk(SUFFOLK_CURRENT, f"DISTRICT = '{DISTRICT}' AND STATUS = 'A'", "PARCELID,SECTION,BLOCK,LOT,CREATEDATE,LASTUPDATE,STATUS")
    historic_rows=_fetch_suffolk(SUFFOLK_HISTORIC, f"DISTRICT = '{DISTRICT}'", "PARCELID,SECTION,BLOCK,LOT,CREATEDATE,LASTUPDATE,STATUS")
    current_by_key={_suffolk_key(a):a for a in current_rows if None not in _suffolk_key(a)}
    historic_by_key={}
    for a in historic_rows:
        hk=_suffolk_key(a)
        if None not in hk: historic_by_key.setdefault(hk,[]).append(a)

    residual_classes=Counter(); residual_details=[]
    for ck in unmatched_canonical:
        ca=current_by_key.get(ck)
        hist=historic_by_key.get(ck,[])
        created=_epoch_iso(ca.get("CREATEDATE")) if ca else None
        if hist:
            cls="CURRENT_KEY_ALSO_IN_HISTORIC"
        elif created and created >= "2025-01-01":
            cls="CURRENT_PARCEL_CREATED_2025_OR_LATER"
        elif created:
            cls="CURRENT_PARCEL_PREDATES_2025_BUT_NO_ORPTS_MATCH"
        else:
            cls="UNRESOLVED_NO_CREATE_DATE"
        residual_classes[cls]+=len(canonical[ck])
        if len(residual_details)<100:
            residual_details.append({
              "normalized_taxmap":"-".join(x for x in ck if x is not None),
              "parcel_ids":canonical[ck][:3],"classification":cls,
              "current_create_date":created,
              "current_last_update":_epoch_iso(ca.get("LASTUPDATE")) if ca else None,
              "historic_exact_key_records":len(hist)
            })

    state_residual_historic=[]
    for sk in unmatched_state[:100]:
        hs=historic_by_key.get(sk,[])
        state_residual_historic.append({
          "normalized_taxmap":"-".join(x for x in sk if x is not None),
          "historic_exact_key_records":len(hs),
          "historic_parcel_ids":[str(x.get("PARCELID")) for x in hs[:5]]
        })

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
      "sample_unmatched_state":["-".join(x for x in k if x is not None) for k in unmatched_state[:25]],
      "sample_unmatched_canonical":[{"normalized_taxmap":"-".join(x for x in k if x is not None),"parcel_ids":canonical[k][:3]} for k in unmatched_canonical[:25]],
      "residual_diagnostic":{
        "unparsable_raw_values":[str(x) for x in unparsable[:100]],
        "unparsable_raw_unique_count":len(set(str(x) for x in unparsable)),
        "all_unmatched_state_keys":["-".join(x for x in k if x is not None) for k in unmatched_state[:100]],
        "unmatched_canonical_sample_count":min(100,len(unmatched_canonical))
      },
      "parcel_lineage_residual_diagnostic":{
        "suffolk_current_records_fetched":len(current_rows),
        "suffolk_historic_records_fetched":len(historic_rows),
        "canonical_residual_class_counts":dict(residual_classes),
        "canonical_residual_details":residual_details,
        "state_residual_historic_exact_key_check":state_residual_historic,
        "classification_limit":"Exact S/B/L and source create/update dates only; no geometry-based parent-child inference is made in V15K8."
      },
      "important_scope_note":"V15K8 preserves the proven V15K7 parser and 97.84% assessment join. It classifies only the remaining residuals using Suffolk current/historic parcel facts and source dates; it does not force lineage matches or persist assessment data.",
      "database_writes":0,"assessment_data_touched":False,"seller_scoring_touched":False,
      "opportunity_data_touched":False,"outreach_touched":False
    }


def _num(v):
    if v in (None, ""): return None
    try: return float(v)
    except (TypeError, ValueError): return None

def _int(v):
    if v in (None, ""): return None
    try: return int(float(v))
    except (TypeError, ValueError): return None

def _ensure_assessment_table(c):
    if backend()=="postgres":
        execute(c,"""CREATE TABLE IF NOT EXISTS assessment_evidence(
          id BIGSERIAL PRIMARY KEY, parcel_id TEXT NOT NULL, source TEXT NOT NULL,
          source_object_id TEXT, roll_year INTEGER NOT NULL, swis TEXT NOT NULL,
          normalized_taxmap TEXT NOT NULL, property_class TEXT, acreage DOUBLE PRECISION,
          assessed_land DOUBLE PRECISION, assessed_total DOUBLE PRECISION,
          full_market_value DOUBLE PRECISION, year_built INTEGER, living_sqft DOUBLE PRECISION,
          bedrooms DOUBLE PRECISION, full_baths DOUBLE PRECISION, parcel_address TEXT,
          building_style TEXT, used_as TEXT, evidence_grade TEXT NOT NULL DEFAULT 'A',
          first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
          UNIQUE(parcel_id,source,roll_year))""")
    else:
        execute(c,"""CREATE TABLE IF NOT EXISTS assessment_evidence(
          id INTEGER PRIMARY KEY AUTOINCREMENT, parcel_id TEXT NOT NULL, source TEXT NOT NULL,
          source_object_id TEXT, roll_year INTEGER NOT NULL, swis TEXT NOT NULL,
          normalized_taxmap TEXT NOT NULL, property_class TEXT, acreage REAL,
          assessed_land REAL, assessed_total REAL, full_market_value REAL,
          year_built INTEGER, living_sqft REAL, bedrooms REAL, full_baths REAL,
          parcel_address TEXT, building_style TEXT, used_as TEXT,
          evidence_grade TEXT NOT NULL DEFAULT 'A', first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL, UNIQUE(parcel_id,source,roll_year))""")
    execute(c,"CREATE INDEX IF NOT EXISTS idx_assessment_evidence_parcel ON assessment_evidence(parcel_id)")

def persist_assessment_v15l():
    """Persist only exact, collision-free 2025 ORPTS-to-current-canonical matches proven by V15K7/V15K8."""
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id,section,block,lot FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchall()
    finally:
        c.close()
    if len(rows)!=EXPECTED_CANONICAL:
        raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {len(rows)}")
    canonical={}
    for r in rows: canonical.setdefault(canonical_key(r[1],r[2],r[3]),[]).append(str(r[0]))
    if any(None in k or len(v)!=1 for k,v in canonical.items()):
        raise RuntimeError("canonical normalization guard failed: null key or collision")

    pages,state_rows=fetch_state_rows()
    parsed=[]
    for a in state_rows:
        k=key_from_sbl(a.get("SBL")) or key_from_sbl(a.get("PRINT_KEY"))
        if k is not None: parsed.append((k,a))
    counts=Counter(k for k,_ in parsed)
    if any(n>1 for n in counts.values()):
        raise RuntimeError("state normalization guard failed: duplicate normalized assessment key")
    state_by_key={k:a for k,a in parsed}
    matched=sorted(set(canonical)&set(state_by_key))
    matched_parcels=sum(len(canonical[k]) for k in matched)
    if matched_parcels!=2490:
        raise RuntimeError(f"proven-match guard failed: expected 2490, found {matched_parcels}")

    now=utc(); inserted=updated=unchanged=0
    c=connect()
    try:
        _ensure_assessment_table(c)
        for k in matched:
            pid=canonical[k][0]; a=state_by_key[k]
            roll=_int(a.get("ROLL_YR"))
            if roll!=2025: raise RuntimeError(f"roll-year guard failed for {pid}: {roll}")
            values=(
              str(a.get("OBJECTID")) if a.get("OBJECTID") is not None else None,
              SWIS,"-".join(k),str(a.get("PROP_CLASS")) if a.get("PROP_CLASS") not in (None,"") else None,
              _num(a.get("ACRES")),_num(a.get("LAND_AV")),_num(a.get("TOTAL_AV")),_num(a.get("FULL_MARKET_VAL")),
              _int(a.get("YR_BLT")),_num(a.get("SQFT_LIVING")),_num(a.get("NBR_BEDROOMS")),_num(a.get("NBR_FULL_BATHS")),
              a.get("PARCEL_ADDR"),a.get("BLDG_STYLE_DESC"),a.get("USED_AS_DESC")
            )
            old=execute(c,"""SELECT source_object_id,swis,normalized_taxmap,property_class,acreage,assessed_land,
                assessed_total,full_market_value,year_built,living_sqft,bedrooms,full_baths,parcel_address,
                building_style,used_as FROM assessment_evidence WHERE parcel_id=? AND source=? AND roll_year=?""",
                (pid,SOURCE,roll)).fetchone()
            if old is None:
                execute(c,"""INSERT INTO assessment_evidence(parcel_id,source,source_object_id,roll_year,swis,
                  normalized_taxmap,property_class,acreage,assessed_land,assessed_total,full_market_value,year_built,
                  living_sqft,bedrooms,full_baths,parcel_address,building_style,used_as,evidence_grade,first_seen_at,last_seen_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (pid,SOURCE,values[0],roll,*values[1:],"A",now,now))
                inserted+=1
            elif tuple(old)==values:
                execute(c,"UPDATE assessment_evidence SET last_seen_at=? WHERE parcel_id=? AND source=? AND roll_year=?",
                        (now,pid,SOURCE,roll)); unchanged+=1
            else:
                execute(c,"""UPDATE assessment_evidence SET source_object_id=?,swis=?,normalized_taxmap=?,property_class=?,
                  acreage=?,assessed_land=?,assessed_total=?,full_market_value=?,year_built=?,living_sqft=?,bedrooms=?,
                  full_baths=?,parcel_address=?,building_style=?,used_as=?,evidence_grade='A',last_seen_at=?
                  WHERE parcel_id=? AND source=? AND roll_year=?""", (*values,now,pid,SOURCE,roll))
                updated+=1
        c.commit()
        total=execute(c,"SELECT COUNT(*) FROM assessment_evidence WHERE source=? AND roll_year=2025",(SOURCE,)).fetchone()[0]
    except Exception:
        c.rollback(); raise
    finally:
        c.close()
    return {
      "status":"ok","version":"V15L","mode":"ASSESSMENT_VALUE_EVIDENCE_PERSISTENCE",
      "database_backend":backend(),"source":SOURCE,"swis":SWIS,"roll_year":2025,"pages":pages,
      "records_fetched":len(state_rows),"canonical_active_parcels":len(rows),"matched_canonical_parcels":matched_parcels,
      "unmatched_canonical_parcels":len(rows)-matched_parcels,"inserted":inserted,"updated":updated,
      "unchanged":unchanged,"persisted_records":total,"evidence_grade":"A","generated_at":utc(),
      "residual_policy":"55 current canonical parcels remain without fabricated 2025 assessment evidence; lineage-sensitive residuals stay unresolved.",
      "seller_scoring_touched":False,"signals_created":0,"events_created":0,"opportunity_data_touched":False,"outreach_touched":False
    }
