#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone

VERSION="V18X"

def _iso_ms(v):
    if v is None: return None
    try:
        return datetime.fromtimestamp(float(v)/1000.0, tz=timezone.utc).date().isoformat()
    except Exception:
        return None

def _norm_id(v):
    if v is None: return None
    s=str(v).strip()
    return s[:-2] if s.endswith(".0") else s

def build_v18x():
    d=json.loads((Path(__file__).with_name("v18x_donor.json")).read_text())
    t=d["target"]; c=d["source_contract"]
    pid=t["parcel_id"]
    params={
      "where":f"PARCELID='{pid}'",
      "outFields":",".join(c["fields"]),
      "returnGeometry":"false",
      "orderByFields":c["order_by"],
      "resultRecordCount":"2000",
      "f":"json"
    }
    url=c["url"]+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"PrivateMarketIntelligence/18X factual-research"})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            payload=json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status":"ok","version":VERSION,"mode":"SINGLE_JUSTIFIED_AUTHORITATIVE_REFRESH_V18W_READ_ONLY",
          "target_parcel_id":pid,"disposition":"SOURCE_INCOMPLETE_OR_AMBIGUOUS",
          "reason":f"Authoritative source request did not complete: {type(e).__name__}",
          "research_may_continue":True,"database_writes":0,
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
    if payload.get("error"):
        return {"status":"ok","version":VERSION,"mode":"SINGLE_JUSTIFIED_AUTHORITATIVE_REFRESH_V18W_READ_ONLY",
          "target_parcel_id":pid,"disposition":"SOURCE_INCOMPLETE_OR_AMBIGUOUS",
          "reason":"Authoritative source returned an error response.","source_error":payload.get("error"),
          "research_may_continue":True,"database_writes":0,
          "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
    rows=[]
    for f in payload.get("features",[]):
        a=f.get("attributes",{})
        rows.append({
          "parcel_id":str(a.get("PARCELID")) if a.get("PARCELID") is not None else None,
          "source_record_id":_norm_id(a.get("DOCNUM")),
          "doccode":a.get("DOCCODE"),
          "recorddate":_iso_ms(a.get("RECORDDATE")),
          "docdate":_iso_ms(a.get("DOCDATE")),
          "entrydate":_iso_ms(a.get("ENTRYDATE")),
          "liberpage":a.get("LIBERPAGE"),
          "transfer_history_sequence":a.get("TRANSHISSEQ")
        })
    remembered={_norm_id(x["source_record_id"]) for x in t["remembered_evidence"]}
    new=[r for r in rows if r["source_record_id"] and r["source_record_id"] not in remembered]
    # "New" here means not in the exact V18W remembered evidence subset; report rows factually.
    disposition="NEW_EVIDENCE_FOUND" if new else "NO_NEW_EVIDENCE"
    return {"status":"ok","version":VERSION,"mode":"SINGLE_JUSTIFIED_AUTHORITATIVE_REFRESH_V18W_READ_ONLY",
      "target_parcel_id":pid,"question":t["question"],
      "disposition":disposition,
      "authoritative_rows_returned":len(rows),
      "remembered_source_identities":sorted(remembered),
      "not_in_v18w_remembered_subset_count":len(new),
      "not_in_v18w_remembered_subset":new,
      "all_authoritative_rows":rows,
      "interpretation_note":"Comparison is against the exact remembered evidence subset carried by V18W. Returned rows are factual source observations; no seller meaning is inferred.",
      "research_may_continue":True,"database_writes":0,
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}

if __name__=="__main__":
    print(json.dumps(build_v18x(),separators=(",",":")))
