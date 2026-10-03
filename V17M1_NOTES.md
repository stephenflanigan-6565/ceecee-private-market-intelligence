V17M1 replaces rejected V17M.

Repair:
- Removes dependency on legacy change_detection.py.
- Uses only db.py plus tables already proven live by V17L1.
- Performs a read-only persistent-memory version check using V16A evidence_key
  and payload_hash semantics.
- Does NOT fetch external sources and does NOT change investigation state.

This is intentionally the safe first half of a true refresh cycle. A later
checkpoint may add controlled source refresh only after this passes live.
