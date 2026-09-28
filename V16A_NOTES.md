# V16A — Persistent Evidence Memory Foundation

Operational foundation for a Suffolk County, multi-market seller-opportunity system. Westhampton Beach is the first configured pilot, not the core architecture.

Creates three portable persistence layers: `market_registry`, `property_market_membership`, and `evidence_ledger`. It seeds the 2,082-property Westhampton residential-side pilot from already-proven property classification, 2025 assessment, Suffolk ownership, and Suffolk transfer/title evidence. Existing raw source tables are not modified.

Evidence rows carry stable evidence keys, source/provenance, evidence family/type, source record identity, event date when valid, evidence grade, quality state, raw normalized payload, first-seen, last-seen, and current-state marker. V15S transfer-date quality policy is preserved: suspect dates remain in evidence but cannot masquerade as valid dated events.

This build does **not** score sellers, create WATCH/INVESTIGATE states, create opportunities, contact owners, or connect optional Southampton permit data. Its purpose is to give the operating engine durable memory so V16B can detect genuinely new/changed evidence instead of rediscovering static facts.

Route: `/api/intelligence/evidence-memory-v16a`

Expected first run: schema created and evidence inserted. Expected second run: no duplicate evidence rows; existing rows are recognized and `last_seen_at` refreshed.
