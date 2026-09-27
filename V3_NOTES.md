# V3 checkpoint

New official-data discovery materially reduces the amount of paid data needed for the pilot.

Suffolk County exposes:
- TaxParcelTransferCurrent: Parcel ID, document identifiers/dates, history sequence, sale date and sale price.
- TaxParcelTransferHistory: Parcel ID plus recorded document/history fields.
- TaxParcelGrantor and TaxParcelGrantee tables keyed by Parcel ID/history sequence.
- TaxParcelHistoricPolygon.
- Current owner table.

V3 adds a transfer ledger and an adapter that backfills official transfer records only for parcels already admitted to the pilot universe. New transfer records create evidence-grade-A events and RECORDED_TRANSFER_ACTIVITY signals.

Important: a recorded transfer is an event, not seller intent. Sale price is used only when supplied by the official current-transfer table. Mortgage/title detail that is not present in these feeds remains a Clerk/deeper-data task.

Next: grantor/grantee linkage, zoning/location enrichment, assessment adapter, then market/listing-history source selection.
