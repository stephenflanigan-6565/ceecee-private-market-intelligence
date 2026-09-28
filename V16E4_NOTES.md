# V16E4 — Suffolk Live Evidence Refresh

Protected baseline: V16D.
Promotion evidence: V16E1 proved runtime access; V16E2 proved the valid parcel-prefix filter and schema; V16E3 proved bounded real-data acquisition.

V16E4 enables persistence for the first time. It acquires the complete 0905 Owner and Transfer History result sets, verifies completeness and prefix containment, intersects them with the 2,082-property market membership, and writes only source observations whose Suffolk OBJECTID is not already persisted.

It does not infer seller intent, score properties, authorize contact, or touch outreach. New source rows remain facts. After a successful run, propagate through V16A -> V16B -> V16C -> V16D.
