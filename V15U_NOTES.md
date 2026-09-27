# V15U — Market Exposure Evidence Rail Readiness

## LOCK
Source: V15T Universal Seller Opportunity Research Framework (PROVEN / LOCKED).

## CHANGE
Adds one read-only diagnostic for the next independent seller-research evidence rail: actual market/listing exposure. It inventories the live database schema for listing/MLS/withdrawal/expiration/relisting fields and defines the minimum evidence/provenance contract for a future authorized source adapter.

## PROTECTED
No changes to V15S guarded transfer logic, V15T universal eligibility, property/ownership/transfer/assessment persistence, seller scoring, WATCH/INVESTIGATE, opportunities, signals, events, or outreach.

## IMPORTANT
V15U intentionally refuses to infer listing history from deeds, transfer age, property age, acreage, size, value, or geography. Absence of listing-history data never removes a property from the universal research universe.

## TEST
GET `/api/westhampton-universe/market-exposure-evidence-readiness-v15u`

Expected: HTTP 200 JSON, 2545 canonical, 2082 residential, zero writes/actions. If no listing-specific persisted source exists, status must be `NOT_YET_CONNECTED` and next action must be source connection/validation—not fabricated inference.
