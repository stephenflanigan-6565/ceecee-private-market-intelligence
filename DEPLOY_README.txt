Canonical name: API Intelligence Targeted Property Assessment Lookup v1

Purpose:
One-property, read-only proof test on parcel 0905017000500015000 / 429A DUNE RD.
Uses existing evidence first to determine whether stored property/assessment evidence can explain the surviving land-vs-improvement assessment anomaly before any external lookup or scaling to the remaining 23 cases.

Endpoint:
/api/intelligence/targeted-property-assessment-lookup-v1

Guards:
- zero database writes
- zero external calls
- no schema changes
- V19V untouched
- no seller scoring/ranking/intent inference
- no contact authorization/outreach
- ownership/title evidence is not accepted as a causal explanation for a property-assessment anomaly

Expected next gate:
If existing evidence reproduces but cannot causally explain the anomaly, authorize exactly one authoritative external property/assessment lookup for this single parcel before scaling.
