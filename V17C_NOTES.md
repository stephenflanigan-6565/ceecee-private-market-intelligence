# V17C — Evidence Resolution & Date-Semantics Repair

Status: BUILT / COMPILE-VERIFIED / LIVE TEST REQUIRED

One change:
Resolve V17B evidence using explicit RECORDDATE / DOCDATE / ENTRYDATE semantics.

Expected important outcomes:
- same-day 2026-06-12 WRDs => RESOLVED_DISTINCT_RECORDED_INSTRUMENTS
- 1112-11-11 => classified as anomalous DOCDATE attached to an identifiable
  1968-05-20 recording at Liber/Page 06349 0317; source value preserved
- incomplete 2026 BSD => retained as an incomplete county row; ENTRYDATE must
  never be substituted for RECORDDATE or Liber/Page
- party-role questions remain unresolved
- zero writes / zero contact authority / zero seller inference
