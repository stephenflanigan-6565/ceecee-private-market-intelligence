# V15F1 — Ownership / Transfer Source Isolation Repair

Scope: diagnose the V15F combined-probe 503 without touching the locked property/classification foundation.

Changes:
- Splits the combined V15F request into independent owner-only and current-transfer-only endpoints.
- Preserves read-only behavior and returns no owner names.
- Adds bounded upstream error classification (HTTP/URL/ArcGIS) so a source failure can be identified without exposing PII.
- No database writes, seller scoring, opportunities, or outreach.

Verification gate:
1. Deploy.
2. Run owner endpoint once.
3. Run transfer endpoint once.
4. Diagnose source coverage/failure independently before any persistence work.
