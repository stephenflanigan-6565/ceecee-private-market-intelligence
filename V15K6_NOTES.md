# V15K6 — Assessment Residual Diagnostic

## Purpose
Read-only diagnostic of the residual NYS ORPTS assessment join after V15K5 reached 2,416 / 2,545 canonical matches (94.93%).

## Allowed change
Expose bounded residual evidence only: raw unparsable SBL/PRINT_KEY values, all parsed unmatched state keys (bounded to 100), and a larger canonical-unmatched sample.

## Protected systems
- V15J ownership + transfer evidence remains locked.
- V15K5 normalization remains unchanged.
- No assessment persistence.
- No seller scoring, signals, opportunities, events, or outreach.
- Database writes remain zero.

## Test objective
Classify the 75 unparsable state tax-map records, 9 parsed unmatched state keys, and remaining canonical misses before any further normalization or persistence change.
