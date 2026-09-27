# V15F2 — Bounded Owner Source Handshake

## Problem isolated
V15F1 owner-only full-district probe returned HTTP 503 twice. The route attempted a potentially long-running district-wide upstream query inside a synchronous Gunicorn web request. Gunicorn's default worker timeout can terminate a request before the urllib 90-second upstream timeout, producing a platform 503 without our JSON diagnostic.

## Allowed change
Add one bounded owner-source handshake only. It selects one already-canonical Westhampton parcel ID from PostgreSQL and asks Suffolk TaxParcelOwner for only that exact PARCELID, requesting only PARCELID and at most one record.

## Protected
No canonical parcel writes. No classification changes. No owner persistence. No transfer persistence. No seller scoring. No opportunities. No outreach.

## Gate
The handshake must return quickly with status ok and database_writes=0. If it does, DigitalOcean-to-Suffolk owner connectivity is proven and the prior 503 is treated as a full-query/request-lifecycle design problem rather than a source outage.
