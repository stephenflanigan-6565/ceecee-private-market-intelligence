# V16W — Operational Investigation Packet Assembly

Status: BUILT / COMPILE-VERIFIED / LIVE TEST REQUIRED

Protected sources:
- V16J durable read-only Investigation Inbox
- V16R1 factual deeper-research resolution
- V16V persisted INVESTIGATE state

Allowed change:
- Add one read-only assembler joining current INVESTIGATE records to already-proven factual research.

Do not touch:
- investigation_state
- V16V promotion/write authority
- Ownership Verification Gate
- Contact Governor
- seller intent/scoring
- outreach
- owner names/addresses
- price/luxury eligibility

Expected live result:
- packet_count = 3
- all_investigate_records_have_factual_research = true
- exact three V16V/V16J INVESTIGATE parcel IDs
- database_writes = false
- investigate_state_touched = false
- contact_authorized = false

Endpoint:
/api/intelligence/operational-investigation-packets-v16w
