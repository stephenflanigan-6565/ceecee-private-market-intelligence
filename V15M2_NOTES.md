# V15M2 — Proven Cohort Source Repair

## Failure isolated
V15M1 safely returned 2,081 residential-side parcels instead of the protected V15E total of 2,082. No writes occurred.

## Root cause
V15M reconstructed the residential-side cohort with SQL shorthand (`2xx` + `31x`) instead of consuming the already-proven V15E persisted classification layer. V15E uses all `2xx` plus an explicit residential-vacant set: 310, 311, 312, 314, 315, 320, 321, 322, 323.

## Repair
V15M2 joins `property_classifications` and selects exactly the two proven V15E cohorts under method `V15D_ORPTS_BROAD_COHORT_V1`. No cohort logic is reimplemented.

## Protection
Read only. No schema change. No persistence. No seller scoring, signals, events, opportunities, or outreach. The 2,545 canonical and 2,082 residential-side guards remain active.
