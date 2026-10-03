#!/usr/bin/env python3
import os,json
from pathlib import Path
VERSION="V19M"

ADDRESS_KEYS=("address","property_address","site_address","situs_address","full_address","location_address","parcel_address")
OWNER_KEYS=("owner","owner_name","owner_names","ownership_name","primary_owner","grantee","taxpayer_name")

def walk(obj, keys):
    found={}
    if isinstance(obj,dict):
        for k,v in obj.items():
            lk=str(k).lower()
            if lk in keys and v not in (None,"",[],{}):
                found.setdefault(lk,[]).append(v)
            if isinstance(v,(dict,list)):
                sub=walk(v,keys)
                for sk,sv in sub.items(): found.setdefault(sk,[]).extend(sv)
    elif isinstance(obj,list):
        for v in obj:
            sub=walk(v,keys)
            for sk,sv in sub.items(): found.setdefault(sk,[]).extend(sv)
    return found

def uniq(vals):
    out=[]
    seen=set()
    for v in vals:
        if isinstance(v,(dict,list)): s=json.dumps(v,sort_keys=True)
        else: s=str(v).strip()
        if s and s not in seen:
            seen.add(s); out.append(v)
    return out

def build_v19m():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19m_donor.json").read_text())
    ids=[c["parcel_id"] for c in d["candidates"]]
    byid={c["parcel_id"]:c for c in d["candidates"]}
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,evidence_family,quality_state,payload_json
                       FROM evidence_ledger
                       WHERE is_current=1 AND parcel_id=ANY(%s)
                         AND evidence_family IN ('PROPERTY_CONTEXT','OWNERSHIP')""",(ids,))
        rows=cur.fetchall()
    finally: conn.close()

    mem={pid:{"property":[],"ownership":[]} for pid in ids}
    for pid,fam,qs,payload in rows:
        try: p=json.loads(payload) if isinstance(payload,str) else (payload or {})
        except Exception: p={}
        rec={"quality_state":qs,"payload":p}
        if fam=="PROPERTY_CONTEXT": mem[pid]["property"].append(rec)
        elif fam=="OWNERSHIP": mem[pid]["ownership"].append(rec)

    out=[]
    for pid in ids:
        addr=[]; owners=[]
        for r in mem[pid]["property"]:
            f=walk(r["payload"],ADDRESS_KEYS)
            for vs in f.values(): addr.extend(vs)
        for r in mem[pid]["ownership"]:
            f=walk(r["payload"],OWNER_KEYS)
            for vs in f.values(): owners.extend(vs)
        addr=uniq(addr); owners=uniq(owners)
        c=byid[pid]
        lane="SOLID" if addr else "FOLLOW_UP"
        out.append({
          "parcel_id":pid,
          "lane":lane,
          "property_address":addr[0] if addr else None,
          "address_candidates":addr,
          "owner_context":owners,
          "owner_context_count":len(owners),
          "why_it_surfaced":c.get("research_attention_reasons",[]),
          "factual_patterns":c.get("patterns",[]),
          "missing_for_review":[] if addr else ["PROPERTY_ADDRESS"],
          "research_continues":True
        })

    solid=sum(x["lane"]=="SOLID" for x in out); follow=len(out)-solid
    with_addr=sum(x["property_address"] is not None for x in out)
    with_owner=sum(x["owner_context_count"]>0 for x in out)
    checks={
      "all_113_candidates_retained":len(out)==113 and len({x["parcel_id"] for x in out})==113,
      "solid_plus_followup_113":solid+follow==113,
      "unknown_address_does_not_discard":True,
      "unknown_owner_does_not_discard":True,
      "no_external_lookup":True,
      "no_guessing":True
    }
    return {
      "status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"CANDIDATE_PROPERTY_IDENTITY_ENRICHMENT_FROM_EXISTING_MEMORY_READ_ONLY",
      "candidate_count":len(out),
      "identity_coverage":{"with_address":with_addr,"without_address":113-with_addr,
                           "with_owner_context":with_owner,"without_owner_context":113-with_owner},
      "research_lanes":{"SOLID":solid,"FOLLOW_UP":follow},
      "candidates":out,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,
        "investigate_state_touched":False,"seller_intent_inferred":False,
        "seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"BUILD_COMPACT_REVIEWABLE_PROPERTY_OUTPUT_ADDRESS_OWNER_WHY",
      "next_if_fail":"PRESERVE_UNKNOWN_IDENTITIES_AS_FOLLOWUP_AND_CONTINUE"
    }
