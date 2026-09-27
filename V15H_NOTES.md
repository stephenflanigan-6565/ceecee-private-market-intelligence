# V15H — Internal Failure Isolation

Purpose: isolate the common failure behind repeated V15F/V15G HTTP 503 responses without touching proven data.

Changes:
- Adds one read-only diagnostic endpoint.
- Uses one canonical PostgreSQL parcel ID.
- Runs three bounded upstream checks independently: proven Parcel service control, Owner service, Transfer History service.
- Captures failure stage (database lookup, network, HTTP, JSON parse, ArcGIS response) and elapsed time.
- Diagnostic endpoint deliberately returns HTTP 200 even when an internal diagnostic test fails, preventing the hosting platform/browser from masking the useful JSON behind a generic 503 page.

Safety:
- Zero database writes.
- No owner/party names requested or returned.
- No scoring, opportunities, Contact Governor, or outreach changes.
- V14/V15B1/V15E proven layers remain untouched.
