# Public and authorized information input

Add an optional `public_information` object beside a native FIND `profiles`
export (or beside the `snapshots` array). It contains `people`,
`property_links`, and `statements`. Existing property-only input still works.
All URLs are inert source locators; this module does not access them.

This synthetic example represents an operator-captured, attributed statement:

```json
{
  "people": [{"person_id": "synthetic-person", "display_name": "SYNTHETIC OWNER"}],
  "property_links": [{
    "person_id": "synthetic-person",
    "parcel_id": "SYNTHETIC-PARCEL",
    "relationship": "OWNER",
    "method": "AUTHORITATIVE_RECORD",
    "source_record_id": "synthetic-current-ownership-record",
    "verified": true,
    "verified_by": "operator"
  }],
  "statements": [{
    "statement_id": "synthetic-statement",
    "person_id": "synthetic-person",
    "quote": "I intend to sell the property identified in this record before buying my next home.",
    "kind": "EXPLICIT_SELL_TO_BUY_PLAN",
    "about": "SELF",
    "access": "PUBLIC",
    "source_record_id": "synthetic-public-post",
    "captured_at": "2026-10-09",
    "current": true,
    "verified": true,
    "verified_by": "operator",
    "parcel_id": "SYNTHETIC-PARCEL",
    "context_tags": ["purchase-and-sale-timing"]
  }]
}
```

The parcel must exist in the supplied property cases. An exact property address
can be supplied instead. `market_code` distinguishes matching identifiers across
markets. Conflicting parcel/address references and ambiguous matches stay
unresolved. A name match can be retained using `NAME_MATCH`, but it does not
establish a verified owner/controller link. `CONTROLLER` is also an allowed
relationship, with a supporting source and operator verification.

`verified` and `verified_by` attest that the operator/source adapter checked the
attribution, meaning, and current identity/control link. The engine does not
authenticate a social account or verify current ownership by opening a URL.
An authoritative historical transfer alone is not a current-owner attestation.

Statement kinds describe the claim's relationship to real estate, rather than
an exhaustive list of life circumstances:

- `EXPLICIT_SELLING_PLAN`: the subject expressed a sale plan.
- `EXPLICIT_BUYING_PLAN`: the subject expressed buying interest; no sale is inferred.
- `EXPLICIT_SELL_TO_BUY_PLAN`: the subject explicitly connected a sale to a purchase.
- `EXPLICIT_HOLD_PLAN`: the subject explicitly plans to retain the referenced property.
- `ANNOUNCED_TRANSITION`: a reported circumstance retained as context.
- `OTHER_CONTEXT`: other attributed public/authorized information.

`context_tags` remain expandable. `about` distinguishes `SELF` from
`THIRD_PARTY`. `access` accepts `PUBLIC` or `AUTHORIZED`. A quotation and a
`source_record_id` or HTTP(S) `source_url` are required for provenance.

Missing capture dates, non-current claims, expired `valid_until` dates,
third-party statements, and unverified attribution remain context. They do not
erase independent property hypotheses. The operator's `current` attestation is
essential: the engine does not assume a recent capture means a recent life event.

For a property-specific sale handoff, the statement itself must identify the
property. Sole ownership of one known property does not establish that an
unreferenced sale statement concerns that property. Such cases remain research
with a consequential identity/property question.

Person findings are retained even when no owned property has been matched.
This supports discovery starting from buying interest and subsequent ownership
research. Announced transitions, age, family details, and location alone never
establish an intention or need to sell. Contact is not authorized by any result.
