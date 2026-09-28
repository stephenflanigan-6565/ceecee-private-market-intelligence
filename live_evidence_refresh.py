#!/usr/bin/env python3
"""V16E — Live Suffolk title/ownership refresh rail.

Fetches the already-proven public Suffolk ArcGIS owner and transfer-history
sources for the configured pilot market, compares the live source to persisted
source evidence, and writes only genuinely new source rows. It does not infer
seller intent or authorize contact. After refresh, V16A/V16B remain responsible
for evidence memory and change detection.
"""
import json, urllib.parse, urllib.request
from datetime import datetime, timezone
from db import connect, execute

VERSION="V16E"
MODE="LIVE_SUFFOLK_TITLE_OWNERSHIP_REFRESH_RAIL"
PILOT="WESTHAMPTON_BEACH_NY"
DISTRICT="0905"
EXPECTED_RESIDENTIAL=2082
OWNER_URL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelOwner/FeatureServer/0/query"
TRANSFER_URL="https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelTransferHistory/FeatureServer/0/query"

def _fetch(url, where, fields):
    out=[]; offset=0
    while True:
        q=urllib.parse.urlencode({"where":where,"outFields":fields,"returnGeometry":"false",
                                  "f":"json","resultOffset":offset,"resultRecordCount":2000,
                                  "orderByFields":"OBJECTID"})
        with urllib.request.urlopen(url+"?"+q,timeout=30) as r:
            data=json.loads(r.read().decode("utf-8"))
        if data.get("error"): raise RuntimeError(str(data["error"]))
        batch=[x.get("attributes",{}) for x in data.get("features",[])]
        out.extend(batch)
        if len(batch)<2000: break
        offset+=len(batch)
    return out

def _cols(c, table):
    try:
        cur=execute(c,f"SELECT * FROM {table} LIMIT 0")
        return [d[0] for d in cur.description]
    except Exception:
        return []

def _norm(v):
    if v is None: return None
    if isinstance(v,float) and v.is_integer(): return int(v)
    return str(v).strip()

def _epoch(v):
    if v in (None,""): return None
    try: return datetime.fromtimestamp(float(v)/1000,timezone.utc).date().isoformat()
    except Exception: return str(v)

def _existing_signatures(c, table, source, fields):
    cols=_cols(c,table)
    use=[x for x in fields if x in cols]
    if not use: return set(),cols
    rows=execute(c,"SELECT "+",".join(use)+f" FROM {table} WHERE source=?",(source,)).fetchall()
    return {tuple(_norm(v) for v in r) for r in rows},cols

def _insert_dynamic(c,table,cols,row):
    use=[k for k in row if k in cols]
    if not use: return False
    execute(c,f"INSERT INTO {table} ("+",".join(use)+") VALUES ("+",".join(["?"]*len(use))+")",
            tuple(row[k] for k in use))
    return True

def refresh_suffolk_title_ownership_v16e():
    c=connect()
    try:
        pids={str(r[0]) for r in execute(c,"SELECT parcel_id FROM property_market_membership WHERE market_code=?",(PILOT,)).fetchall()}
        if len(pids)!=EXPECTED_RESIDENTIAL: raise RuntimeError(f"membership guard failed: {len(pids)}")
        # Public sources are county-wide; district filter keeps acquisition bounded.
        owners=_fetch(OWNER_URL,f"PARCELID LIKE '{DISTRICT}%'","OBJECTID,PARCELID,FIRSTNAME,LASTNAME,OWNERNAME")
        transfers=_fetch(TRANSFER_URL,f"PARCELID LIKE '{DISTRICT}%'","OBJECTID,PARCELID,LIBERPAGE,RECORDDATE,DOCNUM,DOCCODE,DOCDATE,ENTRYDATE,TRANSHISSEQ")
        owners=[x for x in owners if str(x.get("PARCELID")) in pids]
        transfers=[x for x in transfers if str(x.get("PARCELID")) in pids]

        owner_fields=["parcel_id","owner_name","first_name","last_name","source_record_id"]
        transfer_fields=["parcel_id","liber_page","record_date","document_number","document_code","document_date","history_sequence"]
        owner_sig,owner_cols=_existing_signatures(c,"ownership_evidence","Suffolk TaxParcelOwner",owner_fields)
        transfer_sig,transfer_cols=_existing_signatures(c,"transfers","Suffolk TaxParcelTransferHistory",transfer_fields)

        new_owner=[]; new_transfer=[]
        for x in owners:
            row={"parcel_id":str(x.get("PARCELID")),"owner_name":x.get("OWNERNAME"),"first_name":x.get("FIRSTNAME"),
                 "last_name":x.get("LASTNAME"),"source_record_id":str(x.get("OBJECTID")) if x.get("OBJECTID") is not None else None,
                 "source":"Suffolk TaxParcelOwner"}
            sig=tuple(_norm(row.get(k)) for k in owner_fields if k in owner_cols)
            if sig not in owner_sig: new_owner.append(row)
        for x in transfers:
            row={"parcel_id":str(x.get("PARCELID")),"liber_page":x.get("LIBERPAGE"),"record_date":_epoch(x.get("RECORDDATE")),
                 "document_number":x.get("DOCNUM"),"document_code":x.get("DOCCODE"),"document_date":_epoch(x.get("DOCDATE")),
                 "entry_date":_epoch(x.get("ENTRYDATE")),"history_sequence":x.get("TRANSHISSEQ"),
                 "source_record_id":str(x.get("OBJECTID")) if x.get("OBJECTID") is not None else None,
                 "source":"Suffolk TaxParcelTransferHistory"}
            sig=tuple(_norm(row.get(k)) for k in transfer_fields if k in transfer_cols)
            if sig not in transfer_sig: new_transfer.append(row)

        for row in new_owner: _insert_dynamic(c,"ownership_evidence",owner_cols,row)
        for row in new_transfer: _insert_dynamic(c,"transfers",transfer_cols,row)
        c.commit()
        return {"status":"ok","version":VERSION,"mode":MODE,
          "architecture":{"scope":"SUFFOLK_COUNTY_MULTI_MARKET","pilot_market":PILOT,
             "rail":"OFFICIAL_PUBLIC_TITLE_OWNERSHIP_REFRESH","core_logic_market_agnostic":True},
          "live_source":{"owner_records_for_pilot":len(owners),"transfer_records_for_pilot":len(transfers),
             "owner_source":"Suffolk TaxParcelOwner","transfer_source":"Suffolk TaxParcelTransferHistory"},
          "refresh":{"new_owner_source_rows_persisted":len(new_owner),"new_transfer_source_rows_persisted":len(new_transfer),
             "new_source_rows_total":len(new_owner)+len(new_transfer)},
          "guards":{"market_residential_properties":len(pids),"seller_intent_inferred":False,
             "seller_scoring":False,"contact_authorized":False,"outreach_touched":False},
          "pipeline":{"next":"RUN_V16A_THEN_V16B","reason":"V16E refreshes source evidence; V16A records new evidence identities; V16B detects post-baseline change."},
          "next_locked_step":"VERIFY_V16E_THEN_PROPAGATE_THROUGH_V16A_V16B_V16C_V16D"}
    finally: c.close()
