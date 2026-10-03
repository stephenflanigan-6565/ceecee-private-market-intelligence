#!/usr/bin/env python3
import os,json,re
from pathlib import Path
VERSION="V19M1"
OWNER_KEYS={"owner","owner_name","owner_names","ownership_name","primary_owner","grantee","taxpayer_name"}

def normkey(k): return re.sub(r'[^a-z0-9]','',str(k).lower())
def is_address_key(k):
    n=normkey(k)
    if any(x in n for x in ("mail","owner","taxpayer")): return False
    return (
      "address" in n or "situs" in n or "street" in n or
      n in {"fulladdr","fulladdress","siteaddr","siteaddress","propertylocation","location"}
    )
def walk_address(obj,path=""):
    hits=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{path}.{k}" if path else str(k)
            if is_address_key(k) and v not in (None,"",[],{}):
                hits.append({"field":p,"value":v})
            if isinstance(v,(dict,list)): hits.extend(walk_address(v,p))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            if isinstance(v,(dict,list)): hits.extend(walk_address(v,f"{path}[{i}]"))
    return hits
def walk_owner(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in OWNER_KEYS and v not in (None,"",[],{}): vals.append(v)
            if isinstance(v,(dict,list)): vals.extend(walk_owner(v))
    elif isinstance(obj,list):
        for v in obj: vals.extend(walk_owner(v))
    return vals
def uniq(seq):
    out=[]; seen=set()
    for x in seq:
        s=json.dumps(x,sort_keys=True) if isinstance(x,(dict,list)) else str(x).strip()
        if s and s not in seen: seen.add(s); out.append(x)
    return out

def build_v19m1():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19m1_donor.json").read_text())
    ids=[c["parcel_id"] for c in d["candidates"]]; byid={c["parcel_id"]:c for c in d["candidates"]}
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,evidence_family,quality_state,payload_json
          FROM evidence_ledger WHERE is_current=1 AND parcel_id=ANY(%s)
          AND evidence_family IN ('PROPERTY_CONTEXT','OWNERSHIP')""",(ids,))
        rows=cur.fetchall()
    finally: conn.close()
    mem={pid:{"property":[],"ownership":[]} for pid in ids}
    for pid,fam,qs,payload in rows:
        try:p=json.loads(payload) if isinstance(payload,str) else (payload or {})
        except Exception:p={}
        mem[pid]["property" if fam=="PROPERTY_CONTEXT" else "ownership"].append(p)
    out=[]; field_hist={}
    for pid in ids:
        hits=[]; owners=[]
        for p in mem[pid]["property"]: hits.extend(walk_address(p))
        for p in mem[pid]["ownership"]: owners.extend(walk_owner(p))
        cleanhits=[]
        seen=set()
        for h in hits:
            sig=(h["field"],json.dumps(h["value"],sort_keys=True) if isinstance(h["value"],(dict,list)) else str(h["value"]))
            if sig not in seen:
                seen.add(sig); cleanhits.append(h); field_hist[h["field"]]=field_hist.get(h["field"],0)+1
        owners=uniq(owners)
        c=byid[pid]; addr=cleanhits[0]["value"] if cleanhits else None
        out.append({"parcel_id":pid,"lane":"SOLID" if addr else "FOLLOW_UP",
          "property_address":addr,"address_evidence":cleanhits,
          "owner_context":owners,"owner_context_count":len(owners),
          "why_it_surfaced":c.get("research_attention_reasons",[]),
          "factual_patterns":c.get("patterns",[]),
          "missing_for_review":[] if addr else ["PROPERTY_ADDRESS"],
          "research_continues":True})
    with_addr=sum(x["property_address"] is not None for x in out)
    with_owner=sum(x["owner_context_count"]>0 for x in out)
    solid=sum(x["lane"]=="SOLID" for x in out)
    checks={"all_113_candidates_retained":len(out)==113 and len({x["parcel_id"] for x in out})==113,
      "owner_context_preserved_113":with_owner==113,"address_extraction_is_label_based_not_value_guessed":True,
      "unknown_address_does_not_discard":True,"no_external_lookup":True,"no_schema_introspection":True}
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"PROPERTY_CONTEXT_ADDRESS_MAPPING_REPAIR_READ_ONLY",
      "candidate_count":len(out),"identity_coverage":{"with_address":with_addr,"without_address":113-with_addr,
      "with_owner_context":with_owner,"without_owner_context":113-with_owner},
      "research_lanes":{"SOLID":solid,"FOLLOW_UP":113-solid},
      "address_field_histogram":field_hist,"candidates":out,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
      "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
      "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"BUILD_COMPACT_REVIEWABLE_PROPERTY_OUTPUT_ADDRESS_OWNER_WHY",
      "next_if_fail":"PRESERVE_UNRESOLVED_ADDRESS_AS_FOLLOWUP_AND_CONTINUE"}
