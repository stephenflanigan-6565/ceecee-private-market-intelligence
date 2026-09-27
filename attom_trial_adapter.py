#!/usr/bin/env python3
"""
Optional ATTOM adapter boundary.
Requires ATTOM_API_KEY in environment. It is NOT required for the free official-data machine.
Purpose: evaluate whether paid data adds enough non-duplicative history/detail to justify subscription.
"""
import os, json, urllib.parse, urllib.request
BASE="https://api.gateway.attomdata.com/propertyapi/v1.0.0"
KEY=os.getenv("ATTOM_API_KEY")
def call(endpoint,params):
    if not KEY: raise SystemExit("ATTOM_API_KEY is not set")
    req=urllib.request.Request(BASE+endpoint+"?"+urllib.parse.urlencode(params),
        headers={"apikey":KEY,"accept":"application/json","User-Agent":"CEECEE-PMI/6.0"})
    with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
def sales_history(address1,address2):
    return call("/saleshistory/basichistory",{"address1":address1,"address2":address2})
def assessment_history(address1,address2):
    return call("/assessmenthistory/detail",{"address1":address1,"address2":address2})
if __name__=="__main__":
    print("Adapter ready. Supply ATTOM_API_KEY only when trial credentials are authorized.")
