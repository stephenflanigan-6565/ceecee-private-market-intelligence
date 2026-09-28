# V16E4a — Ownership Persistence Schema Repair

Protected baseline: V16D. Acquisition path is unchanged from proven V16E3.

Observed V16E4 failure: PostgreSQL rejected an ownership_evidence insert because required column `source_object_id` was null.

Allowed change only: map Suffolk `OBJECTID` into the existing required `ownership_evidence.source_object_id` column and use that same persisted identity for idempotence.

The refresh remains atomic. Any insertion error rolls the transaction back. No seller inference, scoring, contact authorization, or outreach.
