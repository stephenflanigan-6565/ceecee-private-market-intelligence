# V7 — operating loop

Added the pieces required to turn the research database into an operating system:

- Source-aware refresh schedule.
- Contact Governor table and executable governor pass.
- Buyer-demand book schema.
- CeeCee legacy-relationship import destination.
- Explicit separation between RESEARCH and CONTACT authority.

Initial cadence:
DAILY: current parcel/owner, recorded transfers, buyer matching, outcome scoreboard.
WEEKLY: WATCH/INVESTIGATE re-evaluation.
MONTHLY: location/property context and historic-parcel lineage.
ANNUAL/ON PUBLICATION: assessment roll.
ON DEMAND: paid/deeper enrichment for INVESTIGATE records.

Critical behavior:
An INVESTIGATE record does not authorize outreach. The machine initially sends it to RESEARCH.
Contact requires a later compliance pass plus a legitimate WHY NOW / first-party or campaign basis.

Next genuine external dependencies:
1. deploy collector on an internet-connected runtime;
2. obtain any optional paid-data trial credentials;
3. later import CeeCee legacy exports;
4. later choose/activate outreach stack and compliance process.
