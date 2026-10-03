#!/usr/bin/env python3
"""V18A — Property Intelligence Profile Foundation.
Full residential universe, read-only factual profile assembly.
"""
import json, os
from collections import Counter, defaultdict
from datetime import datetime
import psycopg

VERSION="V18A"
MODE="PROPERTY_INTELLIGENCE_PROFILE_FOUNDATION_READ_ONLY"
FAMILIES=("PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE")

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _date(v):
    if v is None: return None
    s=str(v).strip()
    return s[:10] if len(s)>=10 else s

def _payload(v):
    try: return json.loads(v) if v else {}
    except Exception: return {}

def build_v18a():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,evidence_type,source,source_record_id,
                              event_date,evidence_grade,quality_state,payload_json,is_current
                       FROM evidence_ledger
                       WHERE is_current=1
                       ORDER BY parcel_id,evidence_family,event_date NULLS FIRST,source_record_id""")
        rows=cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='BASELINE'")
        baseline=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investigation_state WHERE state='INVESTIGATE'")
        investigate=cur.fetchone()[0]

    by_parcel=defaultdict(list)
    family_counts=Counter()
    for r in rows:
        by_parcel[r[0]].append(r)
        family_counts[r[1]]+=1

    profiles=[]
    for parcel, evidence in by_parcel.items():
        fam=defaultdict(list)
        quality=Counter()
        sources=set()
        transfer_dates=[]
        transfer_codes=Counter()
        for r in evidence:
            fam[r[1]].append(r)
            quality[str(r[7])]+=1
            sources.add(str(r[3]))
            if r[1]=="TRANSFER_TITLE":
                p=_payload(r[8])
                d=_date(r[5]) or _date(p.get("RECORDDATE"))
                if d: transfer_dates.append(d)
                code=p.get("DOCCODE")
                if code: transfer_codes[str(code)]+=1

        present=[f for f in FAMILIES if fam.get(f)]
        missing=[f for f in FAMILIES if not fam.get(f)]
        transfer_dates=sorted(set(transfer_dates))
        profiles.append({
          "parcel_id":parcel,
          "evidence_rows":len(evidence),
          "families_present":present,
          "families_missing":missing,
          "profile_complete_four_family":len(missing)==0,
          "property_context_rows":len(fam["PROPERTY_CONTEXT"]),
          "assessment_context_rows":len(fam["ASSESSMENT_CONTEXT"]),
          "ownership_rows":len(fam["OWNERSHIP"]),
          "transfer_title_rows":len(fam["TRANSFER_TITLE"]),
          "transfer_recorded_date_first":transfer_dates[0] if transfer_dates else None,
          "transfer_recorded_date_latest":transfer_dates[-1] if transfer_dates else None,
          "transfer_distinct_recorded_dates":len(transfer_dates),
          "transfer_document_codes":dict(sorted(transfer_codes.items())),
          "quality_states":dict(sorted(quality.items())),
          "distinct_sources":len(sources)
        })

    complete=sum(1 for p in profiles if p["profile_complete_four_family"])
    profiles.sort(key=lambda x:x["parcel_id"])
    return {
      "status":"ok","version":VERSION,"mode":MODE,
      "summary":{
        "profiles_built":len(profiles),
        "current_evidence_rows_consumed":len(rows),
        "four_family_complete_profiles":complete,
        "profiles_missing_one_or_more_families":len(profiles)-complete,
        "family_row_counts":dict(sorted(family_counts.items())),
        "baseline_state_count":baseline,
        "investigate_state_count":investigate
      },
      "profile_schema":{
        "identity":"parcel_id",
        "dimensions":["PROPERTY_CONTEXT","ASSESSMENT_CONTEXT","OWNERSHIP","TRANSFER_TITLE"],
        "chronology":["transfer_recorded_date_first","transfer_recorded_date_latest","transfer_distinct_recorded_dates"],
        "data_quality":["families_missing","quality_states","distinct_sources"],
        "purpose":"FACTUAL_LONGITUDINAL_PROPERTY_PROFILE_FOR_LATER_COMPARISON"
      },
      "sample_profiles":profiles[:12],
      "decision_boundary":{
        "full_universe_profile_assembly":True,
        "ranking_performed":False,
        "seller_scoring_performed":False,
        "seller_intent_inferred":False,
        "database_writes":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"BUILD_CROSS_PROPERTY_FACTUAL_COMPARISON_DIMENSIONS_FROM_V18A_PROFILES"
      },
      "guards":{
        "database_writes":False,"investigate_state_touched":False,"new_candidate_created":False,
        "seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,
        "outreach_touched":False,"clerk_kiosk_scraped":False
      }
    }
