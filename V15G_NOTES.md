# V15G — Transfer History Handshake

Purpose: bounded read-only validation of the separate Suffolk County TaxParcelTransferHistory service using one canonical Westhampton Beach parcel already stored in PostgreSQL.

## Change boundary
- Adds a separate TaxParcelTransferHistory endpoint.
- Queries one canonical parcel only.
- Requests at most 5 historical document records.
- Requests no grantor/grantee/owner names.
- Performs no database writes.
- Does not alter canonical parcels, factual cohorts, seller scoring, opportunities, Contact Governor, or outreach.

## Verification gate
Call `/api/westhampton-universe/transfer-history-handshake-v15g`. A JSON response with `status: ok` proves the bounded transfer-history path. Zero historical records is still a successful source handshake if the query itself completes normally.

If the route returns the same infrastructure 503, park this adapter and proceed to the assessment/value layer rather than repeatedly modifying the locked foundation.
