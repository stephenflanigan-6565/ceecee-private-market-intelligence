#!/usr/bin/env python3
"""V18G — Memory Chronology Relationship Resolution.
Read-only. Resolves only the 28 V18F chronology-relationship jobs from persistent memory.
No external retrieval, writes, scoring, seller-intent inference, or state promotion.
"""
import json, os
from collections import Counter, defaultdict
from datetime import date, datetime
import psycopg

VERSION="V18G"

def _dsn():
    for k in ("DATABASE_URL","POSTGRES_URL","POSTGRESQL_URL"):
        if os.getenv(k): return os.getenv(k)
    raise RuntimeError("Database URL environment variable not found")

def _payload(v):
    try:return json.loads(v) if v else {}
    except:return {}

def _first(p,*ks):
    for k in ks:
        v=p.get(k)
        if v not in (None,""): return v
    return None

def _day(v):
    if not v:return None
    try:return datetime.strptime(str(v).strip()[:10],"%Y-%m-%d").date()
    except:return None

def _canon_id(v):
    if v is None:return None
    s=str(v).strip()
    if s.endswith(".0"):s=s[:-2]
    return s

def _event_date(row):
    p=_payload(row[8])
    # Preserve semantics: RECORDDATE first; evidence event_date only as existing stored chronology fallback.
    return _day(_first(p,"RECORDDATE","recorddate","record_date")) or _day(row[5])

def _doccode(row):
    p=_payload(row[8])
    return _first(p,"DOCCODE","doccode","doc_code","document_code")

def build_v18g():
    with psycopg.connect(_dsn()) as conn:
      with conn.cursor() as cur:
        cur.execute("""SELECT parcel_id,evidence_family,evidence_type,source,source_record_id,event_date,
                              evidence_grade,quality_state,payload_json
                       FROM evidence_ledger
                       WHERE is_current=1
                       ORDER BY parcel_id,event_date NULLS FIRST""")
        rows=cur.fetchall()

    by=defaultdict(list)
    for r in rows: by[r[0]].append(r)

    # Exact 28 V18F chronology jobs, preserved from the proven V18F output.
    targets = {
"0905003000200015000":["1192160","1212313","147636","2140200187181","2140200187182","2140200187183","2140200187184","2140200187185","2140200187186","837089"],
"0905006000300004003":["2140200188646","2140200188647","2140200188648","2140200188649","2140200188650","2140200188651","2140200188652","303425","340140","611305","775176"],
"0905007000400016000":["1200054","1223060","2140200189186","2140200189187","2140200189188","2140200189189","2140200189190","2140200189191","817077","865473"],
"0905008000100014002":["120453","159763","186519","2140200189244","2140200189245","2140200189246","2140200189247","2140200189248","2140200189249","2140200189250","2140200189251","2140200189252","2140200189253","2140200189254","217655","43081","492685"],
"0905009000100020000":["1226308","1238113","2140200189680","2140200189681","2140200189682","2140200189683","2140200189684","2140200189685","2140200189686","2140200189687"],
"0905010000300004000":["1236151","213016","2140200190268","2140200190269","2140200190270","2140200190271","2140200190272","2140200190273","2140200190274","2140200190275"],
"0905010000500007000":["2140200190722","2140200190723","2140200190724","2140200190725","2140200190726","2140200190727","404032","703562","703563","703564","808068","808071","830324","859923"],
"0905010000500032000":["1002421","1156283","2140200190894","2140200190895","2140200190896","2140200190897","2140200190898","2140200190899","2140200190900","518483"],
"0905010000500033002":["1206066","162557","2140200190907","2140200190908","2140200190909","2140200190910","2140200190911","2140200190912","562278","906802"],
"0905010000700008000":["1118265","1118268","1118269","2140200191105","2140200191106","2140200191107","2140200191108","2140200191109","2140200191110","2140200191111","487050"],
"0905010000700031011":["1225927","2140200191280","2140200191281","2140200191282","2140200191283","2140200191284","2140200191285","2140200191286","2140200191287","2140200191288","2140200191289","2140200191290","2140200191291","645140"],
"0905010000700031016":["1204125","2140200191332","2140200191333","2140200191334","2140200191335","2140200191336","2140200191337","2140200191338","2140200191339","2140200191340","2140200191341"],
"0905011000200016000":["1225964","2140200191548","2140200191549","2140200191550","2140200191551","2140200191552","2140200191553","2140200191554","2140200191555","2140200191556"],
"0905011010100003000":["1231393","1242516","143114","2140200191977","2140200191978","2140200191979","2140200191980","2140200191981","2140200191982","2140200191983","266241"],
"0905012010200009000":["1204186","2140200192718","2140200192719","2140200192720","2140200192721","2140200192722","2140200192723","2140200192724","273970","578685","622534"],
"0905013000100024004":["2140200192925","2140200192926","2140200192927","2140200192928","2140200192929","287365","321645","325660","331179","331182"],
"0905014000100012000":["1223160","2140200193178","2140200193179","2140200193180","2140200193181","2140200193182","376235","376236","376237","798667","798668"],
"0905015000100014001":["2140200193286","2140200193287"],
"0905015000200014001":["1211910","2140200193362","2140200193363","2140200193364","2140200193365","991362"],
"0905015000300011000":["2140200193493","2140200193494","2140200193495","2140200193496","2140200193497","2140200193498","2140200193499","2140200193500","2140200193501","2140200193502","2140200193503","657052"],
"0905015000400052002":["175838","2140200193721","2140200193722","2140200193723","2140200193724","2140200193725","2140200193726","2140200193727","526899","526900","686113"],
"0905017000200025001":["1185045","2140200194202","2140200194203","2140200194204","2140200194205"],
"0905018000100014000":["107609","181962","2140200194657","2140200194658","2140200194659","2140200194660","41766","576092","664491","915125"],
"0905019020100028000":["1014386","2140200195274","2140200195275","2140200195276","2140200195277","2140200195278","2140200195279","2140200195280","623588","821592"],
"0905019020100046000":["1228622","1228623","2140200195353","2140200195354","2140200195355","2140200195356","2140200195357","2140200195358","254280","717290"],
"0905019030100095000":["1234985","2140200195618","2140200195619","2140200195620","313458","536742","982677"],
"0905020000200030000":["2140200195952","2140200195953"],
"0905021000100003000":["1096758","1096759","1096762","1096765","1107246","1107247","1107248","2140200195974","2140200195975","2140200195976","2140200195977","2140200195978","2140200195979","2140200195980","332254","937098"]
    }

    out=[]; dispositions=Counter()
    for parcel, ids in targets.items():
        wanted=set(ids)
        tr=[r for r in by.get(parcel,[]) if r[1]=="TRANSFER_TITLE" and _canon_id(r[4]) in wanted]
        events=[]
        for r in tr:
            d=_event_date(r); p=_payload(r[8])
            events.append({
                "source_record_id":_canon_id(r[4]),
                "date":d.isoformat() if d else None,
                "doccode":_doccode(r),
                "recorddate":str(_first(p,"RECORDDATE","recorddate","record_date"))[:10] if _first(p,"RECORDDATE","recorddate","record_date") else None,
                "docdate":str(_first(p,"DOCDATE","docdate","doc_date"))[:10] if _first(p,"DOCDATE","docdate","doc_date") else None,
                "liberpage":_first(p,"LIBERPAGE","liberpage","liber_page"),
                "source":r[3]
            })
        events.sort(key=lambda e:(e["date"] or "9999-99-99", e["source_record_id"] or ""))

        dated=[e for e in events if e["date"]]
        dates=sorted(set(_day(e["date"]) for e in dated))
        same_day_groups=defaultdict(list)
        for e in dated:same_day_groups[e["date"]].append(e)
        same_day=[{"date":d,"event_count":len(es),"events":es} for d,es in same_day_groups.items() if len(es)>=2]

        gaps=[]
        for a,b in zip(dates,dates[1:]):
            gaps.append((b-a).days)
        near_pairs=sum(g<=90 for g in gaps)
        long_gaps=sum(g>=730 for g in gaps)

        # Factual classification only. It does not assert legal/substantive causal relationship.
        if len(dated)<2:
            disposition="INDETERMINATE_INSUFFICIENT_DATED_MEMORY"
            explanation="Fewer than two dated target events are available in current memory."
        elif same_day and len(dates)==1:
            disposition="SINGLE_SAME_DAY_EVENT_CLUSTER"
            explanation="All dated target events occur on the same recorded day; memory supports a single temporal cluster but not causal/legal relationship."
        elif long_gaps>=1:
            disposition="SEPARATED_HISTORICAL_EPISODES"
            explanation=f"Target chronology contains {long_gaps} gap(s) of at least two years, supporting distinct temporal episodes in stored history."
        elif near_pairs>=1:
            disposition="TEMPORALLY_CLUSTERED_SEQUENCE"
            explanation=f"Target chronology contains {near_pairs} adjacent event interval(s) of 90 days or less, supporting temporal clustering without inferring motive or causation."
        else:
            disposition="ORDERED_CHRONOLOGY_RELATIONSHIP_INDETERMINATE"
            explanation="Memory establishes event order, but spacing alone does not support classifying the events as one coherent episode or separate historical episodes."

        dispositions[disposition]+=1
        out.append({
            "parcel_id":parcel,
            "target_source_record_count":len(ids),
            "target_events_found":len(events),
            "dated_target_events":len(dated),
            "first_target_date":dated[0]["date"] if dated else None,
            "last_target_date":dated[-1]["date"] if dated else None,
            "same_day_groups":same_day,
            "adjacent_gap_days":gaps,
            "disposition":disposition,
            "explanation":explanation,
            "chronology":events,
            "boundary":"Temporal relationship only. Does not establish seller intent, motivation, distress, legal causation, or outreach priority."
        })

    unresolved=sum(x["disposition"].startswith("INDETERMINATE") or x["disposition"]=="ORDERED_CHRONOLOGY_RELATIONSHIP_INDETERMINATE" for x in out)
    return {
      "status":"ok","version":VERSION,"mode":"MEMORY_CHRONOLOGY_RELATIONSHIP_RESOLUTION_READ_ONLY",
      "summary":{
        "chronology_jobs_expected":28,
        "chronology_jobs_evaluated":len(out),
        "disposition_counts":dict(sorted(dispositions.items())),
        "jobs_remaining_indeterminate":unresolved,
        "jobs_with_memory_supported_temporal_disposition":len(out)-unresolved,
        "evidence_rows_consumed":len(rows),
        "external_research_jobs_touched":0
      },
      "chronology_resolutions":out,
      "decision_boundary":{
        "memory_only":True,"external_research_performed":False,"database_writes":False,
        "seller_score_created":False,"seller_intent_inferred":False,
        "investigate_promotion_authorized":False,
        "next_step_if_clean":"COMBINE_RESOLVED_MEMORY_CHRONOLOGY_WITH_THE_16_ISOLATED_TARGETED_GIS_RECHECK_JOBS"
      },
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}
    }
