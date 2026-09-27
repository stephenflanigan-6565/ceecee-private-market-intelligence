# V15K5 — Canonical Section Suffix Repair

## LOCK → CHANGE → VERIFY → STOP

**Protected baseline:** V15K4 assessment/value source probe.

**Observed live defect:** V15K4 improved the join from 0 to 1,949 matched canonical parcels (76.58%), proving the source and most of the S/B/L normalization. The remaining sample exposed a deterministic section suffix mismatch: canonical `11.01-1-1` versus NYS/ORPTS `11.001-1-1`.

**Allowed change:** Repair only canonical **section** suffix formatting. Suffolk stored section `01101` is normalized to ORPTS `11.001`; whole section `00100` remains `1`. Block and lot normalization are unchanged.

**Protected systems:** V15J ownership/transfer memory, schema, persistence, seller scoring, signals, opportunities, events, Contact Governor, outreach.

**Test objective:** Re-run the existing read-only endpoint `/api/westhampton-universe/assessment-probe-v15k` and measure whether canonical coverage rises above V15K4's 1,949 / 2,545. No database writes are permitted.

**Rollback:** Restore V15K4 `assessment_probe.py`.

## Local verification
- `00100 / 00100 / 01001` → `1-1-1.001`
- `01000 / 00100 / 10000` → `10-1-10`
- `01101 / 00100 / 01000` → `11.001-1-1`
- Python compile: PASS
