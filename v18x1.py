#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone
VERSION="V18X1"

def _iso_ms(v):
    if v is None: return None
    try: return datetime.fromtimestamp(float(v)/1000.0,tz=timezone.utc).date().isoformat()
    except Exception: return None

def _norm(v):
    if v is None: return None
    s=str(v).strip()
    return s[:-2] if s.endswith(".0") else s

def build_v18x1():
    d=json.loads((Path(__file__).with_name("v18x1_donor.json")).read_text())
    t=d["target"]; c=d["source_contract"]; pid=t["parcel_id"]
    params={"where":f"PARCELID='{pid}'","outFields":",".join(c["fields"]),
            "returnGeometry":"false","orderByFields":c["order_by"],
            "resultRecordCount":"2000","f":"json"}
    req=urllib.request.Request(c["url"]+"?"+urllib.parse.urlencode(params),
        headers={"User-Agent":"PrivateMarketIntelligence/18X1 factual-research"})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            payload=json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status":"ok","version":VERSION,"mode":"SINGLE_JUSTIFIED_AUTHORITATIVE_REFRESH_IDENTITY_REPAIR_READ_ONLY",
          "target_parcel_id":pid,"disposition":"SOURCE_INCOMPLETE_OR_AMBIGUOUS",
          "reason":f"Authoritative source request did not complete: {type(e).__name__}",
          "database_writes":0,"research_may_continue":True,"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
    if payload.get("error"):
        return {"status":"ok","version":VERSION,"mode":"SINGLE_JUSTIFIED_AUTHORITATIVE_REFRESH_IDENTITY_REPAIR_READ_ONLY",
          "target_parcel_id":pid,"disposition":"SOURCE_INCOMPLETE_OR_AMBIGUOUS","source_error":payload["error"],
          "database_writes":0,"research_may_continue":True,"guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}
    rows=[]
    for f in payload.get("features",[]):
        a=f.get("attributes",{})
        # Proven Suffolk identity semantics: TRANSHISSEQ is the stable transfer-history identity.
        identity=_norm(a.get("TRANSHISSEQ"))
        rows.append({"parcel_id":str(a.get("PARCELID")) if a.get("PARCELID") is not None else None,
          "source_record_id":identity,"docnum":_norm(a.get("DOCNUM")),"doccode":a.get("DOCCODE"),
          "recorddate":_iso_ms(a.get("RECORDDATE")),"docdate":_iso_ms(a.get("DOCDATE")),
          "entrydate":_iso_ms(a.get("ENTRYDATE")),"liberpage":a.get("LIBERPAGE"),
          "transfer_history_sequence":a.get("TRANSHISSEQ")})
    remembered={_norm(x["source_record_id"]) for x in t["remembered_evidence"]}
    new=[r for r in rows if r["source_record_id"] and r["source_record_id"] not in remembered]
    # Separate genuinely newer/current observations from older historical rows not carried in the tiny V18W subset.
    recent_new=[r for r in new if max([x for x in [r["recorddate"],r["docdate"],r["entrydate"]] if x] or ["0000-00-00"]) >= "2025-10-03"]
    disposition="NEW_RECENT_EVIDENCE_FOUND" if recent_new else ("ADDITIONAL_HISTORICAL_EVIDENCE_FOUND" if new else "NO_NEW_EVIDENCE")
    return {"status":"ok","version":VERSION,"mode":"SINGLE_JUSTIFIED_AUTHORITATIVE_REFRESH_IDENTITY_REPAIR_READ_ONLY",
      "target_parcel_id":pid,"question":t["question"],"disposition":disposition,
      "authoritative_rows_returned":len(rows),"remembered_source_identities":sorted(remembered),
      "not_in_v18w_remembered_subset_count":len(new),"new_recent_evidence_count":len(recent_new),
      "new_recent_evidence":recent_new,"not_in_v18w_remembered_subset":new,"all_authoritative_rows":rows,
      "identity_rule":"TRANSHISSEQ is used as the Suffolk transfer-history source identity; DOCNUM is retained only as source metadata.",
      "database_writes":0,"research_may_continue":True,
      "guards":{"database_writes":False,"investigate_state_touched":False,"seller_intent_inferred":False,"seller_scoring":False,"overall_ranking":False,"contact_authorized":False,"outreach_touched":False}}

if __name__=="__main__": print(json.dumps(build_v18x1(),separators=(",",":")))
