#!/usr/bin/env python3
"""V15M — Westhampton residential derived-intelligence population profile.

READ ONLY. Measures factual distributions across the proven residential-side
universe before any WATCH / INVESTIGATE thresholds are designed.
No signals, events, opportunities, seller scores, or outreach are written.
"""
from collections import Counter
from datetime import datetime, timezone, date
from db import connect, execute, backend

VERSION = "V15M2"
MODE = "READ_ONLY_DERIVED_INTELLIGENCE_POPULATION_PROFILE"
DISTRICT = "0905"
EXPECTED_CANONICAL = 2545
EXPECTED_RESIDENTIAL_SIDE = 2082
ASSESSMENT_SOURCE = "NYS ITS Tax Parcels Public / ORPTS assessment-roll attributes"
ROLL_YEAR = 2025


def utc(): return datetime.now(timezone.utc).isoformat()

def _date(v):
    if v in (None, ""): return None
    s=str(v).strip()[:10]
    for fmt in ("%Y-%m-%d","%m/%d/%Y","%Y%m%d"):
        try: return datetime.strptime(s,fmt).date()
        except ValueError: pass
    return None

def _num(v):
    try: return float(v) if v not in (None,"") else None
    except (TypeError,ValueError): return None

def _int(v):
    try: return int(float(v)) if v not in (None,"") else None
    except (TypeError,ValueError): return None

def _bucket(x, cuts, labels):
    if x is None: return "MISSING"
    for cut,label in zip(cuts,labels):
        if x < cut: return label
    return labels[-1]

def _sorted_counter(c, order):
    return {k:int(c.get(k,0)) for k in order}

def profile_v15m():
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")

        # Reuse the PROVEN/PERSISTED V15E cohort layer directly. Do not
        # reconstruct the cohort with a new SQL shorthand: V15E intentionally
        # defines residential vacant land as a selected exact-code set.
        rows=execute(c,"""
          SELECT p.parcel_id,p.land_use,p.acreage,p.source_created_at,p.source_last_update,
                 a.property_class,a.acreage,a.full_market_value,a.year_built,a.living_sqft,
                 a.bedrooms,a.full_baths
          FROM properties p
          JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          LEFT JOIN assessment_evidence a
            ON a.parcel_id=p.parcel_id AND a.source=? AND a.roll_year=?
          WHERE p.district=? AND p.status='A'
            AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
            AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND')
          ORDER BY p.parcel_id
        """,(ASSESSMENT_SOURCE,ROLL_YEAR,DISTRICT)).fetchall()
        if len(rows) != EXPECTED_RESIDENTIAL_SIDE:
            raise RuntimeError(f"residential-side guard failed: expected {EXPECTED_RESIDENTIAL_SIDE}, found {len(rows)}")

        transfer_rows=execute(c,"""
          SELECT parcel_id,history_sequence,record_date,document_date,sale_date,sale_price
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
        owner_rows=execute(c,"""
          SELECT parcel_id,COUNT(*) FROM ownership_evidence
          WHERE source='Suffolk TaxParcelOwner' GROUP BY parcel_id
        """).fetchall()
    finally:
        c.close()

    transfer_count=Counter(); latest_transfer={}; sale_price_obs=Counter()
    for r in transfer_rows:
        pid=str(r[0]); transfer_count[pid]+=1
        d=_date(r[4]) or _date(r[2]) or _date(r[3])
        if d and (pid not in latest_transfer or d>latest_transfer[pid]): latest_transfer[pid]=d
        if _num(r[5]) not in (None,0): sale_price_obs[pid]+=1
    owner_count={str(r[0]):int(r[1]) for r in owner_rows}

    today=date.today()
    assessment_present=0; year_built_present=0; sqft_present=0; fmv_present=0
    transfer_covered=0; latest_date_present=0; owner_covered=0
    tenure_bins=Counter(); transfer_bins=Counter(); age_bins=Counter(); fmv_bins=Counter(); acreage_bins=Counter()
    owner_party_bins=Counter(); landuse=Counter(); propclass=Counter()

    for r in rows:
        pid=str(r[0]); lu=str(r[1]) if r[1] not in (None,"") else "MISSING"; landuse[lu]+=1
        if owner_count.get(pid,0)>0: owner_covered+=1
        oc=owner_count.get(pid,0)
        owner_party_bins["0" if oc==0 else "1" if oc==1 else "2" if oc==2 else "3+"]+=1

        tc=transfer_count.get(pid,0)
        if tc>0: transfer_covered+=1
        transfer_bins["0" if tc==0 else "1" if tc==1 else "2" if tc==2 else "3-5" if tc<=5 else "6-10" if tc<=10 else "11+"]+=1
        ld=latest_transfer.get(pid)
        if ld:
            latest_date_present+=1
            yrs=(today-ld).days/365.2425
            tenure_bins[_bucket(yrs,[1,3,5,10,20,30,float('inf')],["<1y","1-<3y","3-<5y","5-<10y","10-<20y","20-<30y","30y+"])]+=1
        else: tenure_bins["MISSING"]+=1

        pc=r[5]
        if pc not in (None,""): assessment_present+=1; propclass[str(pc)]+=1
        yb=_int(r[8])
        if yb and 1600 <= yb <= today.year:
            year_built_present+=1
            age=today.year-yb
            age_bins[_bucket(age,[10,25,50,75,100,float('inf')],["<10y","10-<25y","25-<50y","50-<75y","75-<100y","100y+"])]+=1
        else: age_bins["MISSING"]+=1
        sqft=_num(r[9]); sqft_present += int(sqft is not None and sqft>0)
        fmv=_num(r[7])
        if fmv is not None and fmv>0:
            fmv_present+=1
            fmv_bins[_bucket(fmv,[500000,1000000,2000000,3000000,5000000,10000000,float('inf')],["<$500k","$500k-<$1m","$1m-<$2m","$2m-<$3m","$3m-<$5m","$5m-<$10m","$10m+"])]+=1
        else: fmv_bins["MISSING"]+=1
        ac=_num(r[6]) if _num(r[6]) is not None else _num(r[2])
        acreage_bins[_bucket(ac,[0.25,0.5,1,2,5,float('inf')],["<0.25","0.25-<0.5","0.5-<1","1-<2","2-<5","5+"])]+=1 if ac is not None else 0
        if ac is None: acreage_bins["MISSING"]+=1

    n=len(rows)
    return {
      "status":"ok","version":VERSION,"mode":MODE,"database_backend":backend(),"generated_at":utc(),
      "scope":{"district":DISTRICT,"canonical_active_parcels":canonical,"residential_side_parcels":n,
               "residential_definition":"factual source classes: Suffolk LANDUSE 2xx + 31x; guarded to proven V15E total of 2,082"},
      "coverage":{"ownership_evidence_parcels":owner_covered,"transfer_history_parcels":transfer_covered,
                  "latest_transfer_date_parcels":latest_date_present,"assessment_2025_parcels":assessment_present,
                  "year_built_parcels":year_built_present,"living_sqft_parcels":sqft_present,
                  "full_market_value_parcels":fmv_present},
      "distributions":{
        "latest_recorded_transfer_age":_sorted_counter(tenure_bins,["<1y","1-<3y","3-<5y","5-<10y","10-<20y","20-<30y","30y+","MISSING"]),
        "transfer_record_count":_sorted_counter(transfer_bins,["0","1","2","3-5","6-10","11+"]),
        "ownership_evidence_party_count":_sorted_counter(owner_party_bins,["0","1","2","3+"]),
        "property_age_from_2025_assessment":_sorted_counter(age_bins,["<10y","10-<25y","25-<50y","50-<75y","75-<100y","100y+","MISSING"]),
        "2025_full_market_value":_sorted_counter(fmv_bins,["<$500k","$500k-<$1m","$1m-<$2m","$2m-<$3m","$3m-<$5m","$5m-<$10m","$10m+","MISSING"]),
        "acreage":_sorted_counter(acreage_bins,["<0.25","0.25-<0.5","0.5-<1","1-<2","2-<5","5+","MISSING"]),
      },
      "top_property_classes":dict(propclass.most_common(15)),"top_land_use_codes":dict(landuse.most_common(15)),
      "interpretation_limits":[
        "Latest recorded transfer age is not asserted to equal owner tenure; transfer records can reflect events other than an arm's-length ownership change.",
        "2025 full-market value is assessment-roll evidence, not a live appraisal or current sale price.",
        "No distribution bucket is a seller signal or contact authorization in V15M."
      ],
      "database_writes":0,"seller_scoring_touched":False,"signals_created":0,"events_created":0,
      "opportunity_data_touched":False,"outreach_touched":False
    }
