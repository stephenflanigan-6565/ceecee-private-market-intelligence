# V15P — Location Context Profile

READ ONLY. Adds factual location/context measurement to the proven V15N candidate matrix foundation.

## Scope
- Reuses the locked V15E residential cohort: 2,082 parcels.
- Uses persisted parcel address, municipality, ZIP, land use, acreage, assessment characteristics, and transfer history.
- Measures Dune Road only from explicit address text (`DUNE RD` / `DUNE ROAD`).
- Measures seasonal residential (LANDUSE 260), residential vacant land, improved residential, and location/history intersections.

## Explicit limits
- Dune Road does **not** mean waterfront/oceanfront/bayfront.
- No geometry-based waterfront inference is made in V15P.
- No seller score, probability, WATCH/INVESTIGATE promotion, opportunity, event, signal, or outreach is created.
- Zero database writes.

## Purpose
Measure whether factual location context materially changes the candidate population before designing any operational candidate state.
