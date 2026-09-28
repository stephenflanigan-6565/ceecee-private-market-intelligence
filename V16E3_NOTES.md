# V16E3 — Suffolk Bounded Acquisition Proof

Protected baseline: V16D.
V16E2 proved `PARCELID LIKE '0905%'` works for both Owner and Transfer History and proved `DISTRICT = '0905'` is invalid for these layers.

V16E3 proves the real acquisition shape before writes: count plus a 100-row paged data sample using the exact proven parcel-prefix filter and exact returned fields.

Hard guard: zero database writes. Persistence remains disabled until this acquisition test passes.
