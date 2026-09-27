#!/usr/bin/env python3
"""V15M — Westhampton residential derived-intelligence population profile.

READ ONLY. Measures factual distributions across the proven residential-side
universe before any WATCH / INVESTIGATE thresholds are designed.
No signals, events, opportunities, seller scores, or outreach are written.
"""
from collections import Counter
from datetime import datetime, timezone, date
from db import connect, execute, backend

VERSION = "V15N"
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
                 a.property_class,a.acreage,a.full_market_value,a.assessed_total,a.assessed_land,a.year_built,a.living_sqft,
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
    fmv_nonnull=0; fmv_zero=0; assessed_total_nonnull=0; assessed_total_positive=0; assessed_land_nonnull=0; assessed_land_positive=0
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
        yb=_int(r[10])
        if yb and 1600 <= yb <= today.year:
            year_built_present+=1
            age=today.year-yb
            age_bins[_bucket(age,[10,25,50,75,100,float('inf')],["<10y","10-<25y","25-<50y","50-<75y","75-<100y","100y+"])]+=1
        else: age_bins["MISSING"]+=1
        sqft=_num(r[11]); sqft_present += int(sqft is not None and sqft>0)
        fmv=_num(r[7])
        at=_num(r[8]); al=_num(r[9])
        fmv_nonnull += int(fmv is not None); fmv_zero += int(fmv == 0)
        assessed_total_nonnull += int(at is not None); assessed_total_positive += int(at is not None and at>0)
        assessed_land_nonnull += int(al is not None); assessed_land_positive += int(al is not None and al>0)
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
                  "full_market_value_parcels":fmv_present,
                  "assessment_value_diagnostic":{"full_market_value_nonnull":fmv_nonnull,"full_market_value_zero":fmv_zero,
                    "assessed_total_nonnull":assessed_total_nonnull,"assessed_total_positive":assessed_total_positive,
                    "assessed_land_nonnull":assessed_land_nonnull,"assessed_land_positive":assessed_land_positive}},
      "distributions":{
        "latest_recorded_transfer_age":_sorted_counter(tenure_bins,["<1y","1-<3y","3-<5y","5-<10y","10-<20y","20-<30y","30y+","MISSING"]),
        "transfer_record_count":_sorted_counter(transfer_bins,["0","1","2","3-5","6-10","11+"]),
        "ownership_evidence_party_count":_sorted_counter(owner_party_bins,["0","1","2","3+"]),
        "property_age_from_2025_assessment":_sorted_counter(age_bins,["<10y","10-<25y","25-<50y","50-<75y","75-<100y","100y+","MISSING"]),
        "2025_full_market_value": {"status":"SOURCE_UNUSABLE_ALL_ZERO","usable_positive_records":fmv_present,"raw_zero_records":fmv_zero,"note":"Raw source values are preserved in assessment evidence but are not interpreted as market value."},
        "acreage":_sorted_counter(acreage_bins,["<0.25","0.25-<0.5","0.5-<1","1-<2","2-<5","5+","MISSING"]),
      },
      "top_property_classes":dict(propclass.most_common(15)),"top_land_use_codes":dict(landuse.most_common(15)),
      "interpretation_limits":[
        "Latest recorded transfer age is not asserted to equal owner tenure; transfer records can reflect events other than an arm's-length ownership change.",
        "2025 full-market-value is unavailable for intelligence use in this source snapshot because all persisted residential values are zero; raw source values remain preserved.",
        "No distribution bucket is a seller signal or contact authorization in V15M."
      ],
      "database_writes":0,"seller_scoring_touched":False,"signals_created":0,"events_created":0,
      "opportunity_data_touched":False,"outreach_touched":False
    }


def candidate_matrix_v15n():
    """READ ONLY factual candidate matrix. No seller score or contact authorization."""
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        rows=execute(c,"""
          SELECT p.parcel_id,p.land_use,p.acreage,
                 a.property_class,a.year_built,a.living_sqft,a.acreage,
                 a.full_market_value
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
          SELECT parcel_id,record_date,document_date,sale_date
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
        owner_rows=execute(c,"""
          SELECT parcel_id,COUNT(*) FROM ownership_evidence
          WHERE source='Suffolk TaxParcelOwner' GROUP BY parcel_id
        """).fetchall()
    finally:
        c.close()

    latest={}; transfer_count=Counter()
    for r in transfer_rows:
        pid=str(r[0]); transfer_count[pid]+=1
        d=_date(r[3]) or _date(r[1]) or _date(r[2])
        if d and (pid not in latest or d>latest[pid]): latest[pid]=d
    owner_count={str(r[0]):int(r[1]) for r in owner_rows}
    today=date.today()
    dims=Counter(); combos=Counter(); data_quality=Counter(); landuse=Counter()
    for r in rows:
        pid=str(r[0]); lu=str(r[1]) if r[1] not in (None,"") else "MISSING"; landuse[lu]+=1
        ld=latest.get(pid)
        yrs=((today-ld).days/365.2425) if ld else None
        yb=_int(r[4]); age=(today.year-yb) if yb and 1600<=yb<=today.year else None
        ac=_num(r[6]) if _num(r[6]) is not None else _num(r[2])
        sqft=_num(r[5]); tc=transfer_count.get(pid,0); oc=owner_count.get(pid,0)

        t10=yrs is not None and yrs>=10; t20=yrs is not None and yrs>=20; t30=yrs is not None and yrs>=30
        age25=age is not None and age>=25; age50=age is not None and age>=50
        acre1=ac is not None and ac>=1; acre2=ac is not None and ac>=2
        sqft2500=sqft is not None and sqft>=2500; sqft4000=sqft is not None and sqft>=4000
        hist3=tc>=3; hist6=tc>=6; multi_owner=oc>=2
        for key,val in {
          "latest_transfer_10y_plus":t10,"latest_transfer_20y_plus":t20,"latest_transfer_30y_plus":t30,
          "property_age_25y_plus":age25,"property_age_50y_plus":age50,
          "acreage_1_plus":acre1,"acreage_2_plus":acre2,
          "living_sqft_2500_plus":sqft2500,"living_sqft_4000_plus":sqft4000,
          "transfer_history_3_plus":hist3,"transfer_history_6_plus":hist6,
          "ownership_evidence_2_plus_parties":multi_owner}.items():
            dims[key]+=int(val)
        combo_flags={
          "transfer_10y_plus_AND_property_age_25y_plus": t10 and age25,
          "transfer_20y_plus_AND_property_age_25y_plus": t20 and age25,
          "transfer_20y_plus_AND_acreage_1_plus": t20 and acre1,
          "transfer_20y_plus_AND_sqft_2500_plus": t20 and sqft2500,
          "transfer_20y_plus_AND_history_3_plus": t20 and hist3,
          "transfer_20y_plus_AND_age25_AND_acre1": t20 and age25 and acre1,
          "transfer_20y_plus_AND_age25_AND_sqft2500": t20 and age25 and sqft2500,
          "transfer_20y_plus_AND_age25_AND_history3": t20 and age25 and hist3,
          "transfer_30y_plus_AND_age25_AND_history3": t30 and age25 and hist3,
          "transfer_20y_plus_AND_age25_AND_acre1_AND_history3": t20 and age25 and acre1 and hist3,
        }
        for key,val in combo_flags.items(): combos[key]+=int(val)
        complete=sum([ld is not None,age is not None,ac is not None,sqft is not None,tc>0,oc>0])
        data_quality[str(complete)+"/6 factual dimensions present"]+=1

    return {
      "status":"ok","version":"V15N","mode":"READ_ONLY_CANDIDATE_INTELLIGENCE_MATRIX","database_backend":backend(),"generated_at":utc(),
      "scope":{"canonical_active_parcels":canonical,"residential_side_parcels":len(rows),"district":DISTRICT},
      "factual_dimension_counts":dict(dims),
      "intersection_counts":dict(combos),
      "data_completeness":dict(sorted(data_quality.items())),
      "full_market_value_policy":{"status":"SOURCE_UNUSABLE_ALL_ZERO","action":"EXCLUDED_FROM_CANDIDATE_MATRIX","raw_evidence_preserved":True},
      "interpretation_limits":[
        "Counts are factual intersections for population research, not seller scores, seller probabilities, or contact authorization.",
        "Latest recorded transfer age is not asserted to equal owner tenure.",
        "Multiple ownership-evidence parties are descriptive only and are not interpreted as motivation or ownership conflict.",
        "Thresholds in V15N are measurement lenses used to inspect population size; they are not promoted WATCH or INVESTIGATE rules."
      ],
      "database_writes":0,"seller_scoring_touched":False,"signals_created":0,"events_created":0,
      "opportunity_data_touched":False,"outreach_touched":False
    }


def location_context_profile_v15p():
    """READ ONLY location/context profile using persisted factual parcel attributes.

    V15P does not infer waterfront, oceanfront, bayfront, village-core, or seller
    motivation. Dune Road is identified only from the persisted parcel address.
    """
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        rows=execute(c,"""
          SELECT p.parcel_id,p.full_address,p.municipality,p.zipcode,p.land_use,p.acreage,
                 a.year_built,a.living_sqft,a.acreage,
                 pc.cohort
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
          SELECT parcel_id,record_date,document_date,sale_date
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
    finally:
        c.close()

    latest={}
    for r in transfer_rows:
        pid=str(r[0]); d=_date(r[3]) or _date(r[1]) or _date(r[2])
        if d and (pid not in latest or d>latest[pid]): latest[pid]=d

    today=date.today(); counts=Counter(); combos=Counter(); zips=Counter(); municipalities=Counter(); address_coverage=0
    for r in rows:
        pid=str(r[0]); address=(str(r[1]).strip() if r[1] not in (None,'') else '')
        municipality=(str(r[2]).strip() if r[2] not in (None,'') else 'MISSING')
        zipcode=(str(r[3]).strip() if r[3] not in (None,'') else 'MISSING')
        lu=str(r[4]).strip() if r[4] not in (None,'') else 'MISSING'
        cohort=str(r[9])
        if address: address_coverage += 1
        municipalities[municipality]+=1; zips[zipcode]+=1

        au=address.upper()
        # Address-derived corridor only. This deliberately does NOT assert waterfront.
        dune=('DUNE RD' in au or 'DUNE ROAD' in au)
        seasonal=(lu=='260')
        vacant=(cohort=='RESIDENTIAL_VACANT_LAND')
        improved=(cohort=='RESIDENTIAL_IMPROVED')
        ac=_num(r[8]) if _num(r[8]) is not None else _num(r[5])
        yb=_int(r[6]); age=(today.year-yb) if yb and 1600<=yb<=today.year else None
        sqft=_num(r[7])
        ld=latest.get(pid); yrs=((today-ld).days/365.2425) if ld else None
        t10=yrs is not None and yrs>=10; t20=yrs is not None and yrs>=20
        age25=age is not None and age>=25; acre1=ac is not None and ac>=1; sqft2500=sqft is not None and sqft>=2500

        for k,v in {
          'dune_road_address':dune,'seasonal_residential_landuse_260':seasonal,
          'residential_vacant_land':vacant,'residential_improved':improved,
          'acreage_1_plus':acre1,'living_sqft_2500_plus':sqft2500}.items(): counts[k]+=int(v)
        for k,v in {
          'dune_road_AND_transfer_10y_plus':dune and t10,
          'dune_road_AND_transfer_20y_plus':dune and t20,
          'dune_road_AND_age25_plus':dune and age25,
          'dune_road_AND_sqft2500_plus':dune and sqft2500,
          'dune_road_AND_transfer20_AND_age25':dune and t20 and age25,
          'seasonal260_AND_transfer20_plus':seasonal and t20,
          'vacant_land_AND_transfer20_plus':vacant and t20,
          'acre1_plus_AND_transfer20_plus':acre1 and t20,
        }.items(): combos[k]+=int(v)

    return {
      'status':'ok','version':'V15P','mode':'READ_ONLY_LOCATION_CONTEXT_PROFILE','database_backend':backend(),'generated_at':utc(),
      'scope':{'district':DISTRICT,'canonical_active_parcels':canonical,'residential_side_parcels':len(rows)},
      'coverage':{'parcel_address_present':address_coverage,'parcel_address_missing':len(rows)-address_coverage},
      'location_context_counts':dict(counts),
      'location_history_intersections':dict(combos),
      'municipality_values':dict(municipalities.most_common()),
      'zipcode_values':dict(zips.most_common()),
      'interpretation_limits':[
        'Dune Road is identified only by the persisted parcel-address text containing DUNE RD or DUNE ROAD.',
        'Dune Road is a corridor label only; V15P does not infer oceanfront, bayfront, waterfront, view, access, or market value.',
        'Seasonal residential and vacant-land labels come from factual persisted land-use/cohort data; they are not seller signals.',
        'Location/history intersections are population research only and do not authorize WATCH, INVESTIGATE, scoring, or contact.'
      ],
      'database_writes':0,'seller_scoring_touched':False,'signals_created':0,'events_created':0,
      'opportunity_data_touched':False,'outreach_touched':False
    }

# V15Q market configuration: local context is data/configuration, not universal logic.
# Future markets supply their own corridor/context definitions while the cohort engine stays unchanged.
V15Q_MARKET_CONFIG = {
    "market_id": "WESTHAMPTON_BEACH_NY",
    "market_label": "Westhampton Beach",
    "corridors": [
        {"code": "DUNE_ROAD_CORRIDOR", "address_tokens": ["DUNE RD", "DUNE ROAD"]},
    ],
}


def candidate_research_cohorts_v15q():
    """READ ONLY property-level cohort preview across the full proven residential universe.

    Every residential-side parcel is evaluated. Cohorts are overlapping factual research
    lenses, not seller scores, probabilities, WATCH/INVESTIGATE states, or contact authority.
    Local corridor definitions come from V15Q_MARKET_CONFIG so they are replaceable per market.
    """
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        rows=execute(c,"""
          SELECT p.parcel_id,p.full_address,p.land_use,p.acreage,
                 a.year_built,a.living_sqft,a.acreage,
                 pc.cohort
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
          SELECT parcel_id,record_date,document_date,sale_date
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
        owner_rows=execute(c,"""
          SELECT parcel_id,COUNT(*) FROM ownership_evidence
          WHERE source='Suffolk TaxParcelOwner' GROUP BY parcel_id
        """).fetchall()
    finally:
        c.close()

    latest={}; transfer_count=Counter()
    for r in transfer_rows:
        pid=str(r[0]); transfer_count[pid]+=1
        d=_date(r[3]) or _date(r[1]) or _date(r[2])
        if d and (pid not in latest or d>latest[pid]): latest[pid]=d
    owner_count={str(r[0]):int(r[1]) for r in owner_rows}

    today=date.today()
    cohort_members={
        "DUNE_ROAD_HISTORY_RESEARCH":[],
        "SEASONAL_RESIDENTIAL_HISTORY_RESEARCH":[],
        "VACANT_RESIDENTIAL_LAND_HISTORY_RESEARCH":[],
        "LARGER_LOT_HISTORY_RESEARCH":[],
        "LARGER_IMPROVEMENT_HISTORY_RESEARCH":[],
        "GENERAL_IMPROVED_HISTORY_RESEARCH":[],
    }
    properties_with_any=set()

    for r in rows:
        pid=str(r[0]); address=str(r[1]).strip() if r[1] not in (None,'') else None
        lu=str(r[2]).strip() if r[2] not in (None,'') else None
        factual_cohort=str(r[7])
        ac=_num(r[6]) if _num(r[6]) is not None else _num(r[3])
        yb=_int(r[4]); age=(today.year-yb) if yb and 1600<=yb<=today.year else None
        sqft=_num(r[5]); tc=transfer_count.get(pid,0); oc=owner_count.get(pid,0)
        ld=latest.get(pid); yrs=((today-ld).days/365.2425) if ld else None

        t10=yrs is not None and yrs>=10; t20=yrs is not None and yrs>=20
        age25=age is not None and age>=25; acre1=ac is not None and ac>=1
        sqft2500=sqft is not None and sqft>=2500; hist3=tc>=3
        au=(address or '').upper()
        corridor_codes=[]
        for cfg in V15Q_MARKET_CONFIG["corridors"]:
            if any(tok in au for tok in cfg["address_tokens"]): corridor_codes.append(cfg["code"])
        dune="DUNE_ROAD_CORRIDOR" in corridor_codes
        seasonal=(lu=='260'); vacant=(factual_cohort=='RESIDENTIAL_VACANT_LAND'); improved=(factual_cohort=='RESIDENTIAL_IMPROVED')

        reasons=[]
        if t10: reasons.append("LATEST_TRANSFER_10Y_PLUS")
        if t20: reasons.append("LATEST_TRANSFER_20Y_PLUS")
        if age25: reasons.append("PROPERTY_AGE_25Y_PLUS")
        if acre1: reasons.append("ACREAGE_1_PLUS")
        if sqft2500: reasons.append("LIVING_SQFT_2500_PLUS")
        if hist3: reasons.append("TRANSFER_HISTORY_3_PLUS")
        if seasonal: reasons.append("SEASONAL_RESIDENTIAL_LANDUSE_260")
        if vacant: reasons.append("RESIDENTIAL_VACANT_LAND")
        reasons.extend(corridor_codes)

        base={
            "parcel_id":pid,"address":address,"factual_cohort":factual_cohort,"land_use":lu,
            "latest_recorded_transfer_date":ld.isoformat() if ld else None,
            "latest_recorded_transfer_age_years":round(yrs,1) if yrs is not None else None,
            "transfer_history_records":tc,"ownership_evidence_records":oc,
            "property_age_years":age,"acreage":ac,"living_sqft":sqft,
            "reason_codes":reasons,
        }
        memberships=[]
        if dune and t10: memberships.append("DUNE_ROAD_HISTORY_RESEARCH")
        if seasonal and t20: memberships.append("SEASONAL_RESIDENTIAL_HISTORY_RESEARCH")
        if vacant and t20: memberships.append("VACANT_RESIDENTIAL_LAND_HISTORY_RESEARCH")
        if acre1 and t20: memberships.append("LARGER_LOT_HISTORY_RESEARCH")
        if sqft2500 and t20: memberships.append("LARGER_IMPROVEMENT_HISTORY_RESEARCH")
        if improved and t20 and age25 and hist3: memberships.append("GENERAL_IMPROVED_HISTORY_RESEARCH")
        for name in memberships:
            item=dict(base); item["research_cohort"]=name
            cohort_members[name].append(item); properties_with_any.add(pid)

    counts={k:len(v) for k,v in cohort_members.items()}
    # Full property-level membership is returned so the preview is auditable; cohorts may overlap.
    return {
      "status":"ok","version":"V15Q","mode":"READ_ONLY_CANDIDATE_RESEARCH_COHORT_PREVIEW",
      "database_backend":backend(),"generated_at":utc(),
      "market_config":{"market_id":V15Q_MARKET_CONFIG["market_id"],"market_label":V15Q_MARKET_CONFIG["market_label"],
                       "corridor_codes":[x["code"] for x in V15Q_MARKET_CONFIG["corridors"]],
                       "architecture":"BUILD_ONCE_CONFIGURE_BY_MARKET_MEASURE_LOCALLY"},
      "scope":{"district":DISTRICT,"canonical_active_parcels":canonical,"residential_side_parcels":len(rows),
               "all_residential_parcels_evaluated":True},
      "cohort_counts":counts,"unique_properties_in_one_or_more_research_cohorts":len(properties_with_any),
      "cohort_members":cohort_members,
      "cohort_definitions":{
        "DUNE_ROAD_HISTORY_RESEARCH":"Configured local corridor + latest recorded transfer 10y+.",
        "SEASONAL_RESIDENTIAL_HISTORY_RESEARCH":"Land-use 260 + latest recorded transfer 20y+.",
        "VACANT_RESIDENTIAL_LAND_HISTORY_RESEARCH":"Persisted residential-vacant cohort + latest recorded transfer 20y+.",
        "LARGER_LOT_HISTORY_RESEARCH":"Acreage 1+ + latest recorded transfer 20y+.",
        "LARGER_IMPROVEMENT_HISTORY_RESEARCH":"Living area 2,500+ sqft + latest recorded transfer 20y+.",
        "GENERAL_IMPROVED_HISTORY_RESEARCH":"Persisted improved-residential cohort + latest recorded transfer 20y+ + property age 25y+ + 3+ transfer-history records."
      },
      "interpretation_limits":[
        "Westhampton Beach is the pilot market; Dune Road is only one configured local cohort and is not required for inclusion elsewhere.",
        "Research cohorts overlap and are factual lenses only; membership is not a seller score, probability, WATCH/INVESTIGATE state, ranking, or contact authorization.",
        "Latest recorded transfer age is not asserted to equal owner tenure.",
        "Thresholds remain research lenses and are not universal rules; future markets are measured locally and use market configuration rather than hard-coded Westhampton assumptions."
      ],
      "database_writes":0,"seller_scoring_touched":False,"signals_created":0,"events_created":0,
      "opportunity_data_touched":False,"outreach_touched":False
    }

# V15R — transfer-date data-quality guard. Raw evidence is never rewritten.
# Derived intelligence may consume only dates that pass this conservative plausibility window.
V15R_MIN_TRANSFER_DATE = date(1800, 1, 1)


def _transfer_date_quality(d, today=None):
    today = today or date.today()
    if d is None:
        return "MISSING"
    if d > today:
        return "SUSPECT_FUTURE_DATE"
    if d < V15R_MIN_TRANSFER_DATE:
        return "SUSPECT_PRE_1800_DATE"
    return "VALID"


def transfer_date_quality_guard_v15r():
    """READ ONLY diagnostic for transfer-date plausibility across the full residential universe.

    Preserves raw transfer evidence. Produces a valid-only derived latest-transfer date and
    quantifies which parcels/cohort memberships would change if suspect dates are excluded.
    """
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        residential_rows=execute(c,"""
          SELECT p.parcel_id,p.full_address,pc.cohort,p.land_use,p.acreage,
                 a.year_built,a.living_sqft,a.acreage
          FROM properties p
          JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          LEFT JOIN assessment_evidence a
            ON a.parcel_id=p.parcel_id AND a.source=? AND a.roll_year=?
          WHERE p.district=? AND p.status='A'
            AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
            AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND')
          ORDER BY p.parcel_id
        """,(ASSESSMENT_SOURCE,ROLL_YEAR,DISTRICT)).fetchall()
        if len(residential_rows) != EXPECTED_RESIDENTIAL_SIDE:
            raise RuntimeError(f"residential-side guard failed: expected {EXPECTED_RESIDENTIAL_SIDE}, found {len(residential_rows)}")
        transfer_rows=execute(c,"""
          SELECT parcel_id,record_date,document_date,sale_date
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
    finally:
        c.close()

    residential_ids={str(r[0]) for r in residential_rows}
    today=date.today()
    quality_counts=Counter(); suspect=[]
    raw_latest={}; valid_latest={}; valid_count=Counter(); raw_count=Counter()

    for r in transfer_rows:
        pid=str(r[0])
        if pid not in residential_ids:
            continue
        d=_date(r[3]) or _date(r[1]) or _date(r[2])
        q=_transfer_date_quality(d,today)
        quality_counts[q]+=1; raw_count[pid]+=1
        if d and (pid not in raw_latest or d>raw_latest[pid]): raw_latest[pid]=d
        if q == "VALID":
            valid_count[pid]+=1
            if pid not in valid_latest or d>valid_latest[pid]: valid_latest[pid]=d
        elif q.startswith("SUSPECT"):
            suspect.append({
                "parcel_id":pid,
                "raw_selected_date":d.isoformat() if d else None,
                "quality_state":q,
                "record_date":str(r[1]) if r[1] is not None else None,
                "document_date":str(r[2]) if r[2] is not None else None,
                "sale_date":str(r[3]) if r[3] is not None else None,
            })

    # Compare only the latest-date-derived research memberships. This is impact measurement,
    # not a mutation of V15Q and not a seller decision.
    changed_latest=[]; raw_members=set(); guarded_members=set()
    for r in residential_rows:
        pid=str(r[0]); address=str(r[1]).strip() if r[1] not in (None,'') else None
        factual=str(r[2]); lu=str(r[3]).strip() if r[3] not in (None,'') else None
        ac=_num(r[7]) if _num(r[7]) is not None else _num(r[4]); yb=_int(r[5]); sqft=_num(r[6])
        age=(today.year-yb) if yb and 1600<=yb<=today.year else None
        au=(address or '').upper(); dune=any(any(tok in au for tok in cfg['address_tokens']) for cfg in V15Q_MARKET_CONFIG['corridors'])
        seasonal=(lu=='260'); vacant=(factual=='RESIDENTIAL_VACANT_LAND'); improved=(factual=='RESIDENTIAL_IMPROVED')
        hist3=raw_count.get(pid,0)>=3; age25=age is not None and age>=25; acre1=ac is not None and ac>=1; sqft2500=sqft is not None and sqft>=2500

        def memberships(ld):
            yrs=((today-ld).days/365.2425) if ld else None
            t10=yrs is not None and yrs>=10; t20=yrs is not None and yrs>=20
            out=set()
            if dune and t10: out.add('DUNE_ROAD_HISTORY_RESEARCH')
            if seasonal and t20: out.add('SEASONAL_RESIDENTIAL_HISTORY_RESEARCH')
            if vacant and t20: out.add('VACANT_RESIDENTIAL_LAND_HISTORY_RESEARCH')
            if acre1 and t20: out.add('LARGER_LOT_HISTORY_RESEARCH')
            if sqft2500 and t20: out.add('LARGER_IMPROVEMENT_HISTORY_RESEARCH')
            if improved and t20 and age25 and hist3: out.add('GENERAL_IMPROVED_HISTORY_RESEARCH')
            return out

        rm=memberships(raw_latest.get(pid)); gm=memberships(valid_latest.get(pid))
        raw_members.update((pid,x) for x in rm); guarded_members.update((pid,x) for x in gm)
        if raw_latest.get(pid) != valid_latest.get(pid):
            changed_latest.append({
                'parcel_id':pid,'address':address,
                'raw_latest_transfer_date':raw_latest[pid].isoformat() if pid in raw_latest else None,
                'guarded_latest_transfer_date':valid_latest[pid].isoformat() if pid in valid_latest else None,
                'raw_memberships':sorted(rm),'guarded_memberships':sorted(gm),
            })

    removed=sorted(raw_members-guarded_members); added=sorted(guarded_members-raw_members)
    return {
      'status':'ok','version':'V15R','mode':'READ_ONLY_TRANSFER_DATE_DATA_QUALITY_GUARD',
      'database_backend':backend(),'generated_at':utc(),
      'scope':{'district':DISTRICT,'canonical_active_parcels':canonical,'residential_side_parcels':len(residential_rows),
               'all_residential_parcels_evaluated':True},
      'policy':{'raw_evidence_preserved':True,'minimum_plausible_transfer_date':V15R_MIN_TRANSFER_DATE.isoformat(),
                'future_dates_suspect':True,'suspect_dates_excluded_from_derived_latest_date':True},
      'transfer_record_quality_counts':dict(quality_counts),
      'suspect_transfer_record_count':len(suspect),'suspect_transfer_records':suspect,
      'parcels_with_changed_latest_date_after_guard':len(changed_latest),
      'changed_latest_date_details':changed_latest,
      'v15q_membership_impact':{'raw_membership_pairs':len(raw_members),'guarded_membership_pairs':len(guarded_members),
                                'memberships_removed_by_guard':len(removed),'memberships_added_by_guard':len(added),
                                'removed_pairs':[{'parcel_id':p,'research_cohort':c} for p,c in removed],
                                'added_pairs':[{'parcel_id':p,'research_cohort':c} for p,c in added]},
      'interpretation_limits':[
        'V15R does not delete, rewrite, or correct raw Suffolk transfer evidence.',
        'A SUSPECT date is a data-quality state, not evidence about a seller or property owner.',
        'The 1800 floor is a conservative derived-intelligence plausibility guard, not a claim that older historical land records cannot exist.',
        'V15R measures impact only; it does not modify V15Q, create WATCH/INVESTIGATE states, score sellers, or authorize contact.'
      ],
      'database_writes':0,'seller_scoring_touched':False,'signals_created':0,'events_created':0,
      'opportunity_data_touched':False,'outreach_touched':False
    }
