# V12 — Clean Portability Gate
- Remaining generated-ID call sites in parcel and transfer collectors now use the portable DB cursor helper.
- Static portability audit excludes helper implementation and passes only when operating modules have no direct SQLite connection or `.lastrowid`.
- Local bootstrap/runtime smoke suite required to pass before packaging.
- Outreach remains locked OFF.
- Next proof is real PostgreSQL + internet-connected source integration.
