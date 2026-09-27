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


# V15S — reusable guarded transfer intelligence foundation.
# This is the single upstream derivation path for transfer dates used by new intelligence modules.
def _guarded_transfer_intelligence(transfer_rows, residential_ids=None, today=None):
    today = today or date.today()
    raw_count=Counter(); valid_count=Counter(); quality_counts=Counter()
    raw_latest={}; valid_latest={}; suspect_by_parcel=Counter()
    for r in transfer_rows:
        pid=str(r[0])
        if residential_ids is not None and pid not in residential_ids:
            continue
        d=_date(r[3]) or _date(r[1]) or _date(r[2])
        q=_transfer_date_quality(d,today)
        raw_count[pid]+=1; quality_counts[q]+=1
        if d and (pid not in raw_latest or d>raw_latest[pid]): raw_latest[pid]=d
        if q == "VALID":
            valid_count[pid]+=1
            if pid not in valid_latest or d>valid_latest[pid]: valid_latest[pid]=d
        elif q.startswith("SUSPECT"):
            suspect_by_parcel[pid]+=1
    return {
        "raw_count":raw_count,"valid_count":valid_count,"quality_counts":quality_counts,
        "raw_latest":raw_latest,"valid_latest":valid_latest,"suspect_by_parcel":suspect_by_parcel,
    }


def transfer_intelligence_foundation_v15s():
    """READ ONLY proof that the V15R guard is reusable as an upstream intelligence foundation."""
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        residential_rows=execute(c,"""
          SELECT p.parcel_id,p.full_address
          FROM properties p
          JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          WHERE p.district=? AND p.status='A'
            AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
            AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND')
          ORDER BY p.parcel_id
        """,(DISTRICT,)).fetchall()
        if len(residential_rows) != EXPECTED_RESIDENTIAL_SIDE:
            raise RuntimeError(f"residential-side guard failed: expected {EXPECTED_RESIDENTIAL_SIDE}, found {len(residential_rows)}")
        transfer_rows=execute(c,"""
          SELECT parcel_id,record_date,document_date,sale_date
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
    finally:
        c.close()

    ids={str(r[0]) for r in residential_rows}; today=date.today()
    g=_guarded_transfer_intelligence(transfer_rows,ids,today)
    changed=[]; no_valid=[]
    for r in residential_rows:
        pid=str(r[0]); raw=g['raw_latest'].get(pid); valid=g['valid_latest'].get(pid)
        if raw != valid:
            item={"parcel_id":pid,"address":str(r[1]).strip() if r[1] not in (None,'') else None,
                  "raw_latest_transfer_date":raw.isoformat() if raw else None,
                  "guarded_latest_transfer_date":valid.isoformat() if valid else None,
                  "suspect_transfer_records":int(g['suspect_by_parcel'].get(pid,0)),
                  "guarded_latest_quality":"VALID" if valid else "NO_VALID_TRANSFER_DATE"}
            changed.append(item)
            if valid is None: no_valid.append(pid)
    return {
      "status":"ok","version":"V15S","mode":"READ_ONLY_GUARDED_TRANSFER_INTELLIGENCE_FOUNDATION",
      "database_backend":backend(),"generated_at":utc(),
      "scope":{"district":DISTRICT,"canonical_active_parcels":canonical,"residential_side_parcels":len(residential_rows),
               "all_residential_parcels_evaluated":True},
      "foundation_policy":{"raw_evidence_preserved":True,"minimum_plausible_transfer_date":V15R_MIN_TRANSFER_DATE.isoformat(),
                           "future_dates_suspect":True,"derived_modules_use_guarded_latest_transfer_date":True,
                           "missing_valid_date_is_not_imputed":True},
      "transfer_record_quality_counts":dict(g['quality_counts']),
      "parcels_with_any_valid_transfer_date":len(g['valid_latest']),
      "parcels_with_suspect_transfer_records":len(g['suspect_by_parcel']),
      "parcels_with_changed_latest_date_after_guard":len(changed),
      "parcels_with_no_valid_transfer_date_after_guard":len(no_valid),
      "changed_latest_date_details":changed,
      "foundation_contract":[
        "New derived-intelligence modules consume guarded_latest_transfer_date, not raw latest transfer date.",
        "Raw Suffolk transfer evidence remains immutable and auditable.",
        "A missing guarded date remains missing; V15S does not invent tenure or seller intent.",
        "Transfer date and transfer age are factual research dimensions, never universal seller-eligibility gates."
      ],
      "database_writes":0,"seller_scoring_touched":False,"signals_created":0,"events_created":0,
      "opportunity_data_touched":False,"outreach_touched":False
    }

# V15T — universal seller-opportunity research framework.
# Every residential-side property remains eligible. This layer separates factual research
# pathways from context lenses and does NOT create WATCH/INVESTIGATE states or seller scores.
def seller_opportunity_research_framework_v15t():
    """READ ONLY universal eligibility + factual research-pathway preview.

    Purpose: prove that the seller-opportunity architecture starts with the entire residential
    universe and that no price, luxury, acreage, improvement-size, or named-corridor gate can
    remove a property from research eligibility. Existing facts are organized into independent
    research pathways; they are not interpreted as seller intent.
    """
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        rows=execute(c,"""
          SELECT p.parcel_id,p.full_address,p.land_use,p.acreage,
                 pc.cohort,a.year_built,a.living_sqft,a.acreage
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

    ids={str(r[0]) for r in rows}; today=date.today()
    g=_guarded_transfer_intelligence(transfer_rows,ids,today)
    owner_count={str(r[0]):int(r[1]) for r in owner_rows}

    pathway_counts=Counter(); context_counts=Counter(); coverage=Counter()
    pathway_examples={
        "GUARDED_TRANSFER_GAP_20Y_PLUS":[],
        "VALID_TRANSFER_HISTORY_3_PLUS":[],
        "COMBINED_TRANSFER_HISTORY_RESEARCH":[],
        "NO_VALID_TRANSFER_DATE_RESEARCH_GAP":[],
    }
    any_path=set(); no_current_path=[]

    for r in rows:
        pid=str(r[0]); address=str(r[1]).strip() if r[1] not in (None,'') else None
        lu=str(r[2]).strip() if r[2] not in (None,'') else None
        factual=str(r[4]); yb=_int(r[5]); sqft=_num(r[6])
        ac=_num(r[7]) if _num(r[7]) is not None else _num(r[3])
        valid_latest=g['valid_latest'].get(pid); valid_tc=int(g['valid_count'].get(pid,0)); raw_tc=int(g['raw_count'].get(pid,0))
        yrs=((today-valid_latest).days/365.2425) if valid_latest else None
        oc=owner_count.get(pid,0); age=(today.year-yb) if yb and 1600<=yb<=today.year else None

        if address: coverage['address_present']+=1
        if oc>0: coverage['ownership_evidence_present']+=1
        if valid_latest: coverage['guarded_latest_transfer_present']+=1
        if yb and 1600<=yb<=today.year: coverage['year_built_present']+=1
        if ac is not None: coverage['acreage_present']+=1
        if sqft is not None and sqft>0: coverage['living_sqft_present']+=1

        long_gap=yrs is not None and yrs>=20
        deep_history=valid_tc>=3
        no_valid=(valid_latest is None)
        combined=long_gap and deep_history

        active=[]
        if long_gap: active.append('GUARDED_TRANSFER_GAP_20Y_PLUS')
        if deep_history: active.append('VALID_TRANSFER_HISTORY_3_PLUS')
        if combined: active.append('COMBINED_TRANSFER_HISTORY_RESEARCH')
        if no_valid: active.append('NO_VALID_TRANSFER_DATE_RESEARCH_GAP')
        for p in active:
            pathway_counts[p]+=1; any_path.add(pid)
            if len(pathway_examples[p])<25:
                pathway_examples[p].append({
                    'parcel_id':pid,'address':address,'factual_cohort':factual,
                    'guarded_latest_transfer_date':valid_latest.isoformat() if valid_latest else None,
                    'guarded_latest_transfer_age_years':round(yrs,1) if yrs is not None else None,
                    'valid_transfer_history_records':valid_tc,'raw_transfer_history_records':raw_tc,
                    'ownership_evidence_records':oc,
                })
        if not active and len(no_current_path)<25:
            no_current_path.append({'parcel_id':pid,'address':address,'factual_cohort':factual})

        # Context is deliberately separate from seller-opportunity research pathways.
        if factual=='RESIDENTIAL_VACANT_LAND': context_counts['RESIDENTIAL_VACANT_LAND']+=1
        if lu=='260': context_counts['SEASONAL_RESIDENTIAL_LANDUSE_260']+=1
        if age is not None and age>=25: context_counts['PROPERTY_AGE_25Y_PLUS']+=1
        if ac is not None and ac>=1: context_counts['ACREAGE_1_PLUS']+=1
        if sqft is not None and sqft>=2500: context_counts['LIVING_SQFT_2500_PLUS']+=1

    no_path_count=len(rows)-len(any_path)
    return {
      'status':'ok','version':'V15T','mode':'READ_ONLY_UNIVERSAL_SELLER_OPPORTUNITY_RESEARCH_FRAMEWORK',
      'database_backend':backend(),'generated_at':utc(),
      'scope':{'district':DISTRICT,'canonical_active_parcels':canonical,'residential_side_parcels':len(rows),
               'all_residential_parcels_evaluated':True,'universal_research_eligible_parcels':len(rows)},
      'eligibility_contract':{
        'price_floor':False,'luxury_floor':False,'property_size_floor':False,'geographic_prestige_requirement':False,
        'dune_road_requirement':False,'acreage_requirement':False,'improvement_size_requirement':False,
        'every_residential_property_remains_eligible':True,
      },
      'current_factual_research_pathway_counts':dict(pathway_counts),
      'properties_with_one_or_more_current_research_pathways':len(any_path),
      'properties_with_no_current_research_pathway_from_available_facts':no_path_count,
      'context_lens_counts_not_used_as_eligibility_gates':dict(context_counts),
      'coverage':dict(coverage),
      'bounded_pathway_examples':pathway_examples,
      'bounded_no_current_path_examples':no_current_path,
      'pathway_definitions':{
        'GUARDED_TRANSFER_GAP_20Y_PLUS':'Guarded latest valid transfer is at least 20 years old. Research fact only; not owner tenure or seller intent.',
        'VALID_TRANSFER_HISTORY_3_PLUS':'At least three valid transfer-history records after V15S date-quality filtering. Research fact only.',
        'COMBINED_TRANSFER_HISTORY_RESEARCH':'Both guarded 20y+ transfer gap and 3+ valid transfer-history records. Intersection for research, not scoring.',
        'NO_VALID_TRANSFER_DATE_RESEARCH_GAP':'No valid transfer date remains after the V15S guard. This is a data/research gap, not a seller signal.'
      },
      'next_evidence_rails_not_yet_available_in_this_layer':[
        'listing / withdrawal / repeated market-exposure history',
        'parcel / permit / property-change events',
        'agent legacy relationship and Mojo history',
        'genuine buyer-demand match',
        'first-party owner engagement / response'
      ],
      'interpretation_limits':[
        'V15T proves universal seller-opportunity research eligibility; it does not create WATCH or INVESTIGATE states.',
        'A research pathway is a reason to inspect facts, not evidence that an owner wants or needs to sell.',
        'Property age, acreage, living area, land use, price, and named corridors are context lenses only and cannot exclude a property.',
        'Transfer age is derived only from the V15S guarded latest valid transfer date and is not asserted to equal owner tenure.',
        'The current pathway set is intentionally incomplete until additional evidence rails are connected.'
      ],
      'database_writes':0,'seller_scoring_touched':False,'signals_created':0,'events_created':0,
      'watch_state_touched':False,'investigate_state_touched':False,'opportunity_data_touched':False,'outreach_touched':False
    }

# V15U — market-exposure evidence rail readiness diagnostic.
# This does NOT infer listing history from transfers or property characteristics.
def market_exposure_evidence_readiness_v15u():
    """READ ONLY: inventory whether a real listing/market-exposure evidence source is already persisted.

    V15U deliberately refuses to manufacture market exposure from deed transfers, age, acreage,
    value, or property type. It inventories the live schema and defines the evidence contract that
    a future listing-history adapter must satisfy before this rail can influence research.
    """
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        residential=execute(c,"""
          SELECT COUNT(*)
          FROM properties p JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          WHERE p.district=? AND p.status='A'
            AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
            AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND')
        """,(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL or residential != EXPECTED_RESIDENTIAL_SIDE:
            raise RuntimeError(f"universe guard failed: canonical={canonical}, residential={residential}")

        if backend() == 'postgres':
            schema_rows=execute(c,"""
              SELECT table_name,column_name
              FROM information_schema.columns
              WHERE table_schema='public'
              ORDER BY table_name,ordinal_position
            """).fetchall()
        else:
            tables=execute(c,"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            schema_rows=[]
            for t in tables:
                tn=str(t[0])
                for col in execute(c,f'PRAGMA table_info("{tn}")').fetchall():
                    schema_rows.append((tn,str(col[1])))
    finally:
        c.close()

    by_table={}
    for table,col in schema_rows:
        by_table.setdefault(str(table),[]).append(str(col))
    exposure_terms=('listing','listed','list_','mls','withdraw','expire','cancel','market_status','days_on_market','dom','relist')
    candidate_tables={}
    for table,cols in by_table.items():
        hits=sorted({col for col in cols if any(term in col.lower() for term in exposure_terms)})
        if hits or any(term in table.lower() for term in exposure_terms):
            candidate_tables[table]=hits

    # Existing generic event/signal tables are not counted as listing evidence merely because
    # they could store it someday. A qualifying rail requires actual listing-specific persisted fields/source.
    listing_specific_tables={t:cols for t,cols in candidate_tables.items()
                             if any(k in t.lower() for k in ('listing','mls','market_exposure'))}
    ready=bool(listing_specific_tables)
    return {
      'status':'ok','version':'V15U','mode':'READ_ONLY_MARKET_EXPOSURE_EVIDENCE_READINESS',
      'database_backend':backend(),'generated_at':utc(),
      'scope':{'district':DISTRICT,'canonical_active_parcels':canonical,'residential_side_parcels':residential,
               'all_residential_parcels_remain_eligible':True},
      'market_exposure_rail_status':'PERSISTED_SOURCE_PRESENT_REQUIRES_CONTENT_VALIDATION' if ready else 'NOT_YET_CONNECTED',
      'schema_candidate_tables':candidate_tables,
      'listing_specific_persisted_tables':listing_specific_tables,
      'evidence_contract':{
        'required_identity':['parcel_id','source','source_record_id'],
        'required_event_facts':['event_date','market_status_or_event_type'],
        'desired_facts':['list_price','close_price','days_on_market','listing_id','observed_at'],
        'provenance_required':True,'raw_source_preserved':True,'idempotent_ingest_required':True,
        'property_match_must_be_auditable':True,
      },
      'recognized_event_vocabulary_for_future_normalization':[
        'ACTIVE','COMING_SOON','PENDING','CONTRACT','WITHDRAWN','EXPIRED','CANCELED','CLOSED','RELISTED','PRICE_CHANGE','UNKNOWN'
      ],
      'source_policy':[
        'Do not infer listing exposure from deed transfers, transfer age, property age, acreage, size, value, or geography.',
        'Do not scrape or fabricate listing history when a licensed/authorized source is unavailable.',
        'Preserve source-native status text and dates; normalization is additive and auditable.',
        'Market exposure is an independent factual evidence rail, not proof of present seller intent.',
        'No property loses universal research eligibility because listing-history data is absent.'
      ],
      'next_action':'CONNECT_AND_VALIDATE_AUTHORIZED_MARKET_EXPOSURE_SOURCE' if not ready else 'VALIDATE_PERSISTED_MARKET_EXPOSURE_CONTENT',
      'database_writes':0,'seller_scoring_touched':False,'signals_created':0,'events_created':0,
      'watch_state_touched':False,'investigate_state_touched':False,'opportunity_data_touched':False,'outreach_touched':False
    }

# V15V — property / parcel change-event evidence rail.
# READ ONLY. Measures actual dated changes already present in authorized persisted evidence.
# Static property characteristics are never converted into change events.
def property_parcel_change_event_evidence_v15v():
    """READ ONLY inventory of auditable property/parcel change-event evidence.

    Current connected evidence supports dated Suffolk transfer/title-history records and
    source-native parcel create/update metadata. Assessment is a single 2025 roll snapshot,
    so V15V explicitly refuses to infer assessment change without a prior comparable roll.
    """
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        residential_rows=execute(c,"""
          SELECT p.parcel_id,p.full_address,p.source_created_at,p.source_last_update,pc.cohort
          FROM properties p JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          WHERE p.district=? AND p.status='A'
            AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
            AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND')
          ORDER BY p.parcel_id
        """,(DISTRICT,)).fetchall()
        if len(residential_rows) != EXPECTED_RESIDENTIAL_SIDE:
            raise RuntimeError(f"residential-side guard failed: expected {EXPECTED_RESIDENTIAL_SIDE}, found {len(residential_rows)}")
        transfer_rows=execute(c,"""
          SELECT parcel_id,record_date,document_date,sale_date,history_sequence
          FROM transfers WHERE source='Suffolk TaxParcelTransferHistory'
        """).fetchall()
        assessment_rows=execute(c,"""
          SELECT parcel_id,roll_year FROM assessment_evidence
          WHERE source=?
        """,(ASSESSMENT_SOURCE,)).fetchall()
    finally:
        c.close()

    ids={str(r[0]) for r in residential_rows}; today=date.today()
    g=_guarded_transfer_intelligence(transfer_rows,ids,today)

    def age_years(d): return (today-d).days/365.2425 if d else None
    def parse_source_date(v):
        d=_date(v)
        return d

    transfer_windows=Counter(); parcel_created_windows=Counter(); parcel_updated_windows=Counter()
    parcel_created_present=0; parcel_updated_present=0
    recent_transfer_examples=[]; recent_created_examples=[]; recent_updated_examples=[]
    addresses={str(r[0]):(str(r[1]).strip() if r[1] not in (None,'') else None) for r in residential_rows}
    cohorts={str(r[0]):str(r[4]) for r in residential_rows}

    for pid,d in g['valid_latest'].items():
        yrs=age_years(d)
        bucket='<=1Y' if yrs<=1 else '<=3Y' if yrs<=3 else '<=5Y' if yrs<=5 else '>5Y'
        transfer_windows[bucket]+=1
        if yrs<=3 and len(recent_transfer_examples)<25:
            recent_transfer_examples.append({'parcel_id':pid,'address':addresses.get(pid),'factual_cohort':cohorts.get(pid),
                                             'event_type':'VALID_RECORDED_TRANSFER_OR_TITLE_EVENT',
                                             'event_date':d.isoformat(),'age_years':round(yrs,1)})

    for r in residential_rows:
        pid=str(r[0]); cd=parse_source_date(r[2]); ud=parse_source_date(r[3])
        if cd:
            parcel_created_present+=1; yrs=age_years(cd)
            bucket='<=1Y' if yrs<=1 else '<=3Y' if yrs<=3 else '<=5Y' if yrs<=5 else '>5Y'; parcel_created_windows[bucket]+=1
            if yrs<=3 and len(recent_created_examples)<25:
                recent_created_examples.append({'parcel_id':pid,'address':addresses.get(pid),'factual_cohort':cohorts.get(pid),
                                                'event_type':'SOURCE_PARCEL_CREATED_METADATA','event_date':cd.isoformat(),'age_years':round(yrs,1)})
        if ud:
            parcel_updated_present+=1; yrs=age_years(ud)
            bucket='<=1Y' if yrs<=1 else '<=3Y' if yrs<=3 else '<=5Y' if yrs<=5 else '>5Y'; parcel_updated_windows[bucket]+=1
            if yrs<=1 and len(recent_updated_examples)<25:
                recent_updated_examples.append({'parcel_id':pid,'address':addresses.get(pid),'factual_cohort':cohorts.get(pid),
                                                'event_type':'SOURCE_PARCEL_LAST_UPDATE_METADATA','event_date':ud.isoformat(),'age_years':round(yrs,1)})

    roll_years=sorted({int(r[1]) for r in assessment_rows if r[1] is not None})
    assessment_change_ready=len(roll_years)>=2
    return {
      'status':'ok','version':'V15V','mode':'READ_ONLY_PROPERTY_PARCEL_CHANGE_EVENT_EVIDENCE',
      'database_backend':backend(),'generated_at':utc(),
      'scope':{'district':DISTRICT,'canonical_active_parcels':canonical,'residential_side_parcels':len(residential_rows),
               'all_residential_parcels_evaluated':True,'all_residential_parcels_remain_eligible':True},
      'connected_change_evidence':{
        'guarded_transfer_or_title_history':{'status':'CONNECTED','date_quality_guard':'V15S','parcels_with_valid_dated_evidence':len(g['valid_latest']),
          'latest_event_age_windows':{k:int(transfer_windows.get(k,0)) for k in ('<=1Y','<=3Y','<=5Y','>5Y')},
          'bounded_recent_examples':recent_transfer_examples},
        'parcel_source_metadata':{'status':'CONNECTED_AS_METADATA_NOT_SELLER_SIGNAL','created_date_present':parcel_created_present,
          'last_update_date_present':parcel_updated_present,
          'created_age_windows':{k:int(parcel_created_windows.get(k,0)) for k in ('<=1Y','<=3Y','<=5Y','>5Y')},
          'last_update_age_windows':{k:int(parcel_updated_windows.get(k,0)) for k in ('<=1Y','<=3Y','<=5Y','>5Y')},
          'bounded_recent_created_examples':recent_created_examples,'bounded_recent_updated_examples':recent_updated_examples},
        'assessment_change_history':{'status':'READY' if assessment_change_ready else 'NOT_YET_COMPARABLE',
          'persisted_roll_years':roll_years,'requires_two_or_more_comparable_rolls':True}
      },
      'change_event_contract':[
        'A change event must have an auditable source, parcel identity, event date, and event type.',
        'V15S date-quality filtering applies to transfer/title dates before they enter this rail.',
        'Source parcel created/updated timestamps are metadata facts and are not automatically physical property changes.',
        'A single assessment roll cannot prove a property-value, building, or assessment change.',
        'Static acreage, square footage, property age, value, land use, or location are context only and are never manufactured into change events.',
        'A factual change event can justify research but is not proof of current seller intent or contact authorization.'
      ],
      'next_missing_change_sources':['comparable prior assessment roll(s)','permit / certificate / building-change history','parcel split / merge lineage with explicit predecessor-successor linkage'],
      'database_writes':0,'seller_scoring_touched':False,'signals_created':0,'events_created':0,
      'watch_state_touched':False,'investigate_state_touched':False,'opportunity_data_touched':False,'outreach_touched':False
    }

# V15W — Southampton permit / certificate / building-change source readiness.
# READ ONLY. Establishes the evidence contract and access boundary before any permit ingestion.
def permit_building_change_source_readiness_v15w():
    c=connect()
    try:
        canonical=execute(c,"SELECT COUNT(*) FROM properties WHERE district=? AND status='A'",(DISTRICT,)).fetchone()[0]
        if canonical != EXPECTED_CANONICAL:
            raise RuntimeError(f"canonical guard failed: expected {EXPECTED_CANONICAL}, found {canonical}")
        residential=execute(c,"""
          SELECT COUNT(*) FROM properties p JOIN property_classifications pc ON pc.parcel_id=p.parcel_id
          WHERE p.district=? AND p.status='A'
            AND pc.method_version='V15D_ORPTS_BROAD_COHORT_V1'
            AND pc.cohort IN ('RESIDENTIAL_IMPROVED','RESIDENTIAL_VACANT_LAND')
        """,(DISTRICT,)).fetchone()[0]
        if residential != EXPECTED_RESIDENTIAL_SIDE:
            raise RuntimeError(f"residential-side guard failed: expected {EXPECTED_RESIDENTIAL_SIDE}, found {residential}")
    finally:
        c.close()

    return {
      'status':'ok','version':'V15W','mode':'READ_ONLY_PERMIT_BUILDING_CHANGE_SOURCE_READINESS',
      'database_backend':backend(),'generated_at':utc(),
      'scope':{'district':DISTRICT,'canonical_active_parcels':canonical,'residential_side_parcels':residential,
               'all_residential_parcels_remain_eligible':True},
      'official_source_readiness':{
        'southampton_gis_eportal':{
          'status':'OFFICIAL_SOURCE_CONFIRMED_ACCESS_CONTROLLED',
          'publisher':'Town of Southampton GIS',
          'documented_content':['permits','certificates of occupancy','certificates of compliance','property data','sales','mass appraisal','scanned property documents'],
          'access':'SUBSCRIPTION_OR_AUTHORIZED_SESSION_REQUIRED_FOR_PROPERTY_LEVEL_RESEARCH'
        },
        'southampton_public_permit_lookup':{
          'status':'OFFICIAL_PUBLIC_LOOKUP_CONFIRMED',
          'publisher':'Town of Southampton',
          'documented_search_modes':['permit number / address','property search','permit status','licensed contractor'],
          'automation_status':'NOT_YET_VALIDATED_FOR_BULK_OR_PROGRAMMATIC_INGEST'
        },
        'southampton_building_forms':{
          'status':'OFFICIAL_EVENT_VOCABULARY_SOURCE',
          'documented_residential_activity_types':['ACCESSORY_STRUCTURE','ADDITION','INTERIOR_RENOVATION_OR_ALTERATION','NEW_DWELLING','PARTIAL_DEMOLITION','POOL_SPA_HOT_TUB','WHOLE_HOUSE_DEMOLITION','CERTIFICATE_OF_OCCUPANCY','CERTIFICATE_OF_COMPLIANCE'],
          'role':'NORMALIZATION_REFERENCE_NOT_PROPERTY_EVENT_FEED'
        }
      },
      'future_evidence_contract':{
        'required_identity':['parcel_id','source','source_record_id'],
        'required_event_facts':['event_date','source_native_event_type_or_description'],
        'desired_facts':['permit_number','permit_status','application_date','issue_date','completion_or_certificate_date','certificate_number','source_native_description'],
        'property_match_must_be_auditable':True,'provenance_required':True,'raw_source_preserved':True,'idempotent_ingest_required':True
      },
      'normalization_policy':[
        'Preserve source-native permit/certificate text; normalized event types are additive.',
        'A permit application, issued permit, inspection, completion, CO, and compliance certificate are distinct facts when the source distinguishes them.',
        'Do not infer completed construction merely from a permit application or issuance.',
        'Do not infer seller intent from permit or building activity.',
        'Do not use static assessment characteristics as substitutes for dated permit/building events.',
        'Do not automate an access-controlled source until authorized access and permitted retrieval method are established.'
      ],
      'rail_status':'SOURCE_CONFIRMED_INGEST_NOT_YET_AUTHORIZED_OR_VALIDATED',
      'next_action':'VALIDATE_PROPERTY_LEVEL_RETRIEVAL_AND_PARCEL_MATCH_WITH_AUTHORIZED_SOUTHAMPTON_ACCESS',
      'credential_or_purchase_required_before_next_ingest_step':True,
      'database_writes':0,'seller_scoring_touched':False,'signals_created':0,'events_created':0,
      'watch_state_touched':False,'investigate_state_touched':False,'opportunity_data_touched':False,'outreach_touched':False
    }
