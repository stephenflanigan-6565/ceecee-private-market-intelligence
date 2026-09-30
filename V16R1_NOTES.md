# V16R1 — factual deeper research resolution KeyError repair

- Exact failure repaired: `_prior()` referenced transfer event key `family`, while V16R constructs normalized transfer events with `event_family`.
- Isolated change only: `family` -> `event_family` in `_prior()`.
- No research rules, queue admission rules, ownership gates, seller-intent rules, contact authorization, outreach behavior, or database-write behavior changed.
- V16Q remains protected prerequisite.
- Compile verification: PASS.
