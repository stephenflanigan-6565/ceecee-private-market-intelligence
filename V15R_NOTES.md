# V15R — Transfer Date Data Quality Guard

Purpose: isolate and measure implausible Suffolk transfer dates before any transfer-age fact can influence future WATCH/INVESTIGATE research.

Protected layers: V15E classification, V15J raw ownership/transfer evidence, V15L assessment evidence, V15Q cohort preview. Raw evidence is never rewritten.

Guard policy:
- VALID: parsed transfer date from 1800-01-01 through today.
- SUSPECT_PRE_1800_DATE: parsed date before 1800-01-01.
- SUSPECT_FUTURE_DATE: parsed date after today.
- MISSING: no parseable selected transfer date.
- Suspect dates are excluded only from V15R's derived latest-transfer calculation.

V15R reports all suspect records, parcels whose derived latest date changes, and the exact V15Q research-membership impact. It performs zero database writes and creates no signals, events, seller scores, opportunities, WATCH/INVESTIGATE states, or outreach.

Endpoint: /api/westhampton-universe/transfer-date-quality-guard-v15r
