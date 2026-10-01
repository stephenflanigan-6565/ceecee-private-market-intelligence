# V16V — Controlled Operational INVESTIGATE State Transition

## Protected sources
- V16D `investigation_state` persistence contract recovered from the original user-supplied V16D package.
- V16U verified read-only promotion governance.

## One allowed change
Persist operational `INVESTIGATE` state for only the three exact parcels that V16U already verified as promotion-eligible:
- 0905004010100063000
- 0905011000300030000
- 0905019020100046000

The two factual-basis records blocked by ownership verification remain untouched:
- 0905008000100037000
- 0905018000200001005

## Hard guards
- V16U must return exactly 32 evaluated items.
- Eligible set must exactly equal the three verified parcel IDs.
- Ownership-blocked set must exactly equal the two verified parcel IDs.
- All five rows must already exist in the proven V16D `investigation_state` table.
- A blocked record already in INVESTIGATE causes an abort with zero V16V writes.
- V16V creates no table and performs no schema migration.
- Contact authorization remains OFF.
- Seller-intent inference remains OFF.
- No seller scoring, motivation/distress inference, owner names/addresses, outreach, price floor, or luxury gate.

## Persistence behavior
V16V updates only the three eligible V16D rows. It preserves the existing V16D `trigger_count` because that field specifically represents V16B change-event count and V16V will not fabricate a V16B trigger. It sets/preserves `first_entered_at`, refreshes `last_evaluated_at`, records the V16U/V16T factual authority in `reason_json`, and hard-resets `contact_authorized=0` and `seller_intent_inferred=0`.

Repeated execution is bounded/idempotent for state: the same three records remain INVESTIGATE; no additional parcels can be admitted without a separately changed and revalidated governance contract.
