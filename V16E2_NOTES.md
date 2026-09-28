# V16E2 — Exact Suffolk Query-Shape Isolation

Protected baseline: V16D.
V16E1 proved all eight basic official Suffolk access paths work from DigitalOcean.
Remaining failure under test: the exact filtered/data-returning query shape used by the failed V16E refresh.

This build compares control queries with DISTRICT and PARCELID LIKE filters for both Owner and Transfer History and returns the actual field names exposed by a one-record response.

Hard guard: zero database writes.
