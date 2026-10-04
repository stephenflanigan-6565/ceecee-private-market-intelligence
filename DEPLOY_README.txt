CANONICAL NAME: API Intelligence Property Anomaly Lab v1.1

Purpose: diagnostic repair of v1 after live schema PASS / zero-candidate result.

Changed files:
- property_anomaly_lab_v1_1.py (NEW)
- web_app.py (adds one endpoint; prior v1 endpoint remains intact)

New endpoint:
/api/intelligence/property-anomaly-lab-v1-1

Repairs / additions:
1. Recognizes live parcel_address field.
2. Transparently derives improvement_assessment = assessed_total - assessed_land when direct field is absent.
3. Adds diagnostic maxima, near-threshold counts, and peer-group sizes so zero results are interpretable.
4. Keeps high-specificity candidate thresholds unchanged for this isolated test.

GUARDS:
READ ONLY. 0 DB writes. No schema changes. No external calls. No V19V state changes.
No seller qualification, seller score, contact authority, or outreach.
