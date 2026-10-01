# V17D — Persistent Authoritative Research Evidence Memory

Status: BUILT / COMPILE-VERIFIED / LIVE PERSISTENCE TEST REQUIRED

Donor: exact V16A Persistent Evidence Memory Foundation uploaded by user.
Reused principles: db.connect/execute, SHA-256 stable evidence keys, append-safe insert,
first_seen/last_seen, identical evidence => last_seen refresh only.

One change:
Persist V17C authoritative county research into a separate additive table:
`authoritative_research_evidence`.

Protected:
- original V16A `evidence_ledger` is not written
- raw source tables are not written
- INVESTIGATE/contact/outreach untouched
- source anomalies are preserved
- RECORDDATE is never fabricated from ENTRYDATE/DOCDATE

Test sequence:
1. Run endpoint once: expect inserts > 0 and protected V16A ledger unchanged.
2. Run endpoint a second time: expect inserted_this_run = 0 and already_known_this_run > 0.
