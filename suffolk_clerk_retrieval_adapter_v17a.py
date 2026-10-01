from datetime import datetime, timezone
from targeted_source_detail_enrichment_v16z import build_targeted_source_detail_enrichment_plan_v16z
VERSION="V17A"
MODE="READ_ONLY_SUFFOLK_CLERK_RETRIEVAL_ADAPTER_CONTRACT"
def _tax(p):
 p=str(p or "").strip(); ok=len(p)==19 and p.isdigit(); return {"valid":ok,"raw":p,"formatted":f"{p[:4]} {p[4:9]} {p[9:13]} {p[13:19]}" if ok else None}
def _window(req):
 ds=[]
 def walk(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if (k.endswith("_date") or k=="event_date") and isinstance(v,str) and len(v)>=10 and v[:4].isdigit() and int(v[:4])>=1987: ds.append(v[:10])
    walk(v)
  elif isinstance(x,list):
   for v in x: walk(v)
 walk(req.get("target_events") or [])
 return {"date_from":min(ds) if ds else None,"date_to":max(ds) if ds else None,"basis":"TARGET_EVENT_DATES" if ds else "NO_RELIABLE_ONLINE_DATE_WINDOW"}
def _job(r):
 target=r.get("authoritative_evidence_target"); rules={"must_match_tax_map":True,"must_preserve_source_provenance":True,"required_identity_fields":["liber","page","recording_date","document_type"],"party_fields_when_available":["grantor","grantee"],"do_not_infer_missing_party_relationships":True,"insufficient_evidence_result":"UNRESOLVED"}
 if target=="SAME_DAY_INSTRUMENT_IDENTITY": rules["resolution_rule"]="Compare authoritative Liber/Page identities; do not call records duplicates solely because dates and document codes match."
 elif target=="RECORDED_INSTRUMENT_DETAIL": rules["resolution_rule"]="Match requested dates/types to Clerk records and report Grantor/Grantee roles and Liber/Page without inferring seller motivation."
 elif target=="HISTORICAL_RECORD_DATE_VALIDATION": rules["resolution_rule"]="Online index coverage is 1987-present; older/anomalous source dates remain unresolved unless separate authoritative historical evidence is obtained."
 return {"research_request_id":r.get("research_request_id"),"parcel_id":r.get("parcel_id"),"clerk_tax_map":_tax(r.get("parcel_id")),"authoritative_source":"SUFFOLK_COUNTY_CLERK_ONLINE_RECORDS","source_class":"AUTHORITATIVE_COUNTY_RECORDING_INDEX","search_basis":"PROPERTY_TAX_MAP_ID","search_window":_window(r),"evidence_target":target,"requested_fields":r.get("required_fields") or [],"acceptance_contract":rules,"retrieval_status":"NOT_EXECUTED","retrieval_reason":"MACHINE_ACCESS_MECHANISM_NOT_YET_VALIDATED","contact_authorized":False,"seller_intent_inferred":False}
def build_suffolk_clerk_retrieval_adapter_contract_v17a():
 s=build_targeted_source_detail_enrichment_plan_v16z(); reqs=s.get("enrichment_requests") or []; jobs=[_job(r) for r in reqs]
 return {"status":"ok","version":VERSION,"mode":MODE,"generated_at":datetime.now(timezone.utc).isoformat(),"market_code":s.get("market_code"),"source_contract":{"version":s.get("version"),"targeted_source_detail_requests":len(reqs)},"authoritative_source_contract":{"source_name":"SUFFOLK_COUNTY_CLERK_ONLINE_RECORDS","search_basis":"PROPERTY_TAX_MAP_ID","online_index_coverage":"1987_PRESENT","metadata_search_login_required":False,"document_image_access":"PAID_SEPARATE_TIER","machine_access_status":"NOT_YET_VALIDATED"},"summary":{"retrieval_jobs_prepared":len(jobs),"valid_tax_map_jobs":sum(1 for j in jobs if j["clerk_tax_map"]["valid"]),"external_retrieval_performed":False,"authoritative_records_ingested":0,"questions_resolved":0},"retrieval_jobs":jobs,"guards":{"database_writes":False,"external_retrieval_performed":False,"investigate_state_touched":False,"new_candidate_created":False,"paid_document_purchase_performed":False,"manual_ownership_verification_bypassed":False,"seller_intent_inferred":False,"seller_scoring":False,"contact_authorized":False,"outreach_touched":False,"source_history_silently_corrected":False}}
