#!/usr/bin/env python3
"""V15K — Westhampton Beach 2026 assessment/value source probe.

READ ONLY. Downloads the official Southampton assessment-roll PDF, extracts
Westhampton Beach tax-map identifiers, normalizes section/block/lot, and
measures the join against the locked canonical Suffolk parcel universe.
No assessment rows are persisted in V15K.
"""
import io, re, urllib.request, urllib.error
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from db import connect, execute, backend

VERSION="V15K"
MODE="READ_ONLY_ASSESSMENT_VALUE_SOURCE_PROBE"
DISTRICT="0905"
SWIS="473607"
EXPECTED_CANONICAL=2545
ROLL_YEAR=2026
SOURCE="Town of Southampton 2026 Assessment Roll — Westhampton Beach"
PDF_URL="https://www.southamptontownny.gov/DocumentCenter/View/46937/Westhampton-Beach-473607"
PDF_MIRROR_URL="https://www.southamptontownnypolice.gov/DocumentCenter/View/46937/Westhampton-Beach-473607"
# Example official roll form: 473607 012.000-0002-035.000
TAXMAP_RE=re.compile(r"\b473607\s+(\d{1,3}(?:\.\d+)?)\s*-\s*(\d{1,4}(?:\.\d+)?)\s*-\s*(\d{1,3}(?:\.\d+)?)\b")

def utc(): return datetime.now(timezone.utc).isoformat()

def norm_component(value):
    s=str(value or "").strip()
    if not s: return None
    try:
        d=Decimal(s)
        if d==d.to_integral(): return str(d.quantize(Decimal(1)))
        return format(d.normalize(),"f")
    except InvalidOperation:
        # Defensive fallback for source formatting: digits and decimal point only.
        s="".join(ch for ch in s if ch.isdigit() or ch==".")
        if not s: return None
        try: return format(Decimal(s).normalize(),"f").rstrip("0").rstrip(".") or "0"
        except InvalidOperation: return None

def key(section,block,lot):
    return (norm_component(section),norm_component(block),norm_component(lot))

def _download_pdf(url, timeout=45):
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0 (compatible; Private-Market-Intelligence/V15K1)",
        "Accept":"application/pdf,*/*;q=0.8",
        "Connection":"close",
    })
    with urllib.request.urlopen(req,timeout=timeout) as r:
        data=r.read()
        ctype=(r.headers.get("Content-Type") or "").lower()
    if len(data)<10000: raise RuntimeError("assessment roll download unexpectedly small")
    if not data.startswith(b"%PDF"): raise RuntimeError(f"assessment roll response is not PDF ({ctype})")
    return data

def fetch_pdf():
    errors=[]
    for url in (PDF_URL, PDF_MIRROR_URL):
        try:
            return _download_pdf(url), url
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
    raise RuntimeError("assessment roll download failed from all official hosts: " + " | ".join(errors))

def extract_taxmaps(pdf_bytes):
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("pypdf dependency missing") from e
    reader=PdfReader(io.BytesIO(pdf_bytes))
    matches=[]; pages_with_taxmaps=0
    for page_no,page in enumerate(reader.pages,1):
        text=page.extract_text() or ""
        page_matches=TAXMAP_RE.findall(text)
        if page_matches:
            pages_with_taxmaps += 1
            matches.extend((page_no,*m) for m in page_matches)
    return len(reader.pages),pages_with_taxmaps,matches

def probe_assessment_v15k():
    c=connect()
    try:
        rows=execute(c,"SELECT parcel_id,section,block,lot FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchall()
    finally: c.close()
    if len(rows)!=EXPECTED_CANONICAL:
        raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {len(rows)}")

    canonical={}
    for r in rows:
        k=key(r[1],r[2],r[3])
        canonical.setdefault(k,[]).append(str(r[0]))
    canonical_collisions={k:v for k,v in canonical.items() if None not in k and len(v)>1}

    pdf,source_url=fetch_pdf()
    page_count,pages_with_taxmaps,matches=extract_taxmaps(pdf)
    raw_keys=[key(sec,blk,lot) for _,sec,blk,lot in matches]
    counts=Counter(raw_keys)
    roll_keys=set(raw_keys)
    matched=roll_keys & set(canonical)
    unmatched_roll=sorted(roll_keys-set(canonical))
    unmatched_canonical=sorted(set(canonical)-roll_keys)
    matched_parcels=sum(len(canonical[k]) for k in matched)

    return {
      "status":"ok","version":VERSION,"mode":MODE,"database_backend":backend(),
      "source":SOURCE,"source_url":source_url,"official_source_urls":[PDF_URL,PDF_MIRROR_URL],"roll_year":ROLL_YEAR,"swis":SWIS,"district":DISTRICT,
      "generated_at":utc(),"pdf_bytes":len(pdf),"pdf_pages":page_count,"pages_with_taxmaps":pages_with_taxmaps,
      "taxmap_occurrences_extracted":len(raw_keys),"unique_roll_taxmaps":len(roll_keys),
      "duplicate_taxmap_occurrences":sum(n-1 for n in counts.values() if n>1),
      "canonical_active_parcels":len(rows),"canonical_unique_normalized_keys":len(canonical),
      "canonical_normalization_collisions":len(canonical_collisions),
      "matched_unique_roll_taxmaps":len(matched),"matched_canonical_parcels":matched_parcels,
      "canonical_match_pct":round(100*matched_parcels/len(rows),2) if rows else 0,
      "unmatched_roll_taxmaps":len(unmatched_roll),"unmatched_canonical_parcels":sum(len(canonical[k]) for k in unmatched_canonical),
      "sample_unmatched_roll":["-".join(x for x in k if x is not None) for k in unmatched_roll[:10]],
      "sample_unmatched_canonical":[{"normalized_taxmap":"-".join(x for x in k if x is not None),"parcel_ids":canonical[k][:3]} for k in unmatched_canonical[:10]],
      "fields_targeted_next":["property_class","acreage","assessed_land","assessed_total","market_value"],
      "database_writes":0,"assessment_data_touched":False,"seller_scoring_touched":False,
      "opportunity_data_touched":False,"outreach_touched":False
    }
