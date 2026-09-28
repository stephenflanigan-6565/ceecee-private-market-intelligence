# V16B — Change Detection Against Evidence Memory

## LOCK
V16A Persistent Evidence Memory Foundation is proven/idempotent at 18,001 ledger rows across all 2,082 Westhampton Beach pilot residential-side properties. V16A and prior source evidence remain protected.

## CHANGE
Adds a Suffolk-wide `evidence_current_state` comparison layer and append-only `evidence_change_events` ledger. Westhampton Beach is only the configured pilot market.

First execution establishes the baseline and MUST create zero change events. Later executions compare the latest V16A observation set against that baseline and can record factual `NEW_EVIDENCE`, `CHANGED_EVIDENCE`, `MISSING_FROM_LATEST_SOURCE_OBSERVATION`, or `REAPPEARED_EVIDENCE` events.

## PROTECTED BOUNDARIES
No seller intent inference. No seller scoring. No WATCH or INVESTIGATE state. No opportunity state. No outreach/contact authorization. No raw source mutation. No mutation of the V16A evidence ledger.

## TEST
1. Deploy.
2. Run `/api/intelligence/change-detection-v16b` once. Expected: initial baseline, zero change events.
3. Run the same endpoint again without a V16A source refresh. Expected: zero new change events and stable state counts.
4. After a future V16A refresh containing genuinely new/changed/missing source evidence, V16B should emit only the factual delta.

## NEXT
After V16B is proven, V16C may interpret factual changes into independent research/opportunity pathways without declaring seller intent or authorizing contact.
