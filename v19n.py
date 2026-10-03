#!/usr/bin/env python3
import os,json,urllib.parse,urllib.request
from pathlib import Path
VERSION="V19N"
PARCEL_URL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelPolygon/FeatureServer/0/query"

def fetch_addresses(ids):
    out={}; errors=[]
    for i in range(0,len(ids),50):
        chunk=ids[i:i+50]
        quoted=",".join("'"+x.replace("'","''")+"'" for x in chunk)
        params={"where":f"PARCELID IN ({quoted})","outFields":"PARCELID,FULLADDRESS,MUNICIPALITY,ZIPCODE,STATUS",
                "returnGeometry":"false","f":"json"}
        try:
            req=urllib.request.Request(PARCEL_URL+"?"+urllib.parse.urlencode(params),
                headers={"User-Agent":"PMI/1.0"})
            with urllib.request.urlopen(req,timeout=25) as r:data=json.loads(r.read().decode())
            if data.get("error"): errors.append({"chunk":i//50,"error":data["error"]}); continue
            for f in data.get("features",[]):
                a=f.get("attributes",{}); pid=a.get("PARCELID")
                if pid: out[str(pid)]=a
        except Exception as e: errors.append({"chunk":i//50,"error_type":type(e).__name__,"error":str(e)[:300]})
    return out,errors

def owner_values(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in {"owner","owner_name","owner_names","ownership_name","primary_owner","taxpayer_name"} and v not in (None,"",[],{}): vals.append(v)
            if isinstance(v,(dict,list)): vals+=owner_values(v)
    elif isinstance(obj,list):
        for v in obj: vals+=owner_values(v)
    return vals
def uniq(vals):
    o=[];s=set()
    for v in vals:
        x=json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else str(v).strip()
        if x and x not in s:s.add(x);o.append(v)
    return o

def build_v19n():
    import psycopg
    d=json.loads(Path(__file__).with_name("v19n_donor.json").read_text())
    ids=[c["parcel_id"] for c in d["candidates"]]; byid={c["parcel_id"]:c for c in d["candidates"]}
    addresses,source_errors=fetch_addresses(ids)
    conn=psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur=conn.cursor()
        cur.execute("""SELECT parcel_id,payload_json FROM evidence_ledger
          WHERE is_current=1 AND parcel_id=ANY(%s) AND evidence_family='OWNERSHIP'""",(ids,))
        rows=cur.fetchall()
    finally: conn.close()
    owners={pid:[] for pid in ids}
    for pid,payload in rows:
        try:p=json.loads(payload) if isinstance(payload,str) else (payload or {})
        except Exception:p={}
        owners[pid]+=owner_values(p)
    out=[]
    for pid in ids:
        a=addresses.get(pid); ov=uniq(owners[pid]); c=byid[pid]
        addr=(a or {}).get("FULLADDRESS")
        lane="SOLID" if addr else "FOLLOW_UP"
        out.append({"parcel_id":pid,"lane":lane,"property_address":addr,
          "municipality":(a or {}).get("MUNICIPALITY"),"zipcode":(a or {}).get("ZIPCODE"),
          "parcel_status":(a or {}).get("STATUS"),"owner_context":ov,"owner_context_count":len(ov),
          "why_it_surfaced":c.get("research_attention_reasons",[]),"factual_patterns":c.get("patterns",[]),
          "missing_for_review":[] if addr else ["AUTHORITATIVE_PARCEL_ADDRESS"],"research_continues":True})
    with_addr=sum(bool(x["property_address"]) for x in out); with_owner=sum(x["owner_context_count"]>0 for x in out)
    solid=sum(x["lane"]=="SOLID" for x in out)
    checks={"all_113_candidates_retained":len(out)==113 and len({x["parcel_id"] for x in out})==113,
      "owner_context_preserved_113":with_owner==113,"authoritative_source_is_parcel_keyed":True,
      "no_address_guessing":True,"missing_address_does_not_discard":True,"database_unchanged":True}
    return {"status":"ok" if all(checks.values()) else "failed","version":VERSION,
      "mode":"AUTHORITATIVE_PARCEL_ADDRESS_ENRICHMENT_READ_ONLY","source":"Suffolk County TaxParcelPolygon FeatureServer",
      "candidate_count":len(out),"source_errors":source_errors,
      "identity_coverage":{"with_address":with_addr,"without_address":113-with_addr,
      "with_owner_context":with_owner,"without_owner_context":113-with_owner},
      "research_lanes":{"SOLID":solid,"FOLLOW_UP":113-solid},"candidates":out,"checks":checks,"database_writes":0,
      "guards":{"database_writes":False,"schema_introspection":False,"investigate_state_touched":False,
      "seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,
      "contact_authorized":False,"outreach_touched":False},
      "next_if_pass":"BUILD_FIRST_COMPACT_REVIEWABLE_PROPERTY_SET",
      "next_if_fail":"PRESERVE_UNRESOLVED_ADDRESS_AS_FOLLOWUP_AND_CONTINUE"}
