# V16F — Controlled Positive Detection Validation

Protected production checkpoint: V16E4c + V16A + V16B + V16C + V16D.

Purpose: prove the positive branch without contaminating production memory. The harness reads the live baseline, creates one explicitly synthetic TRANSFER_TITLE fact in memory, applies the exact locked V16B logical-key/fingerprint/change-key contract, then applies the exact locked V16D rule that a post-baseline factual change creates INVESTIGATE.

No database writes are performed. Production ledger/change-event/investigation counts are captured before and after and must be identical.

This is a logic-path validation, not a claim that a real Suffolk change occurred.
