from datetime import datetime, timezone
from db import backend, connect, execute

MARKER_KEY = "cloud-foundation-persistence-v1"


def verify_persistence():
    """Create/read a harmless infrastructure marker outside property/owner data."""
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        execute(c, """
            CREATE TABLE IF NOT EXISTS cloud_runtime_checks (
                marker_key TEXT PRIMARY KEY,
                first_seen_utc TEXT NOT NULL,
                last_seen_utc TEXT NOT NULL,
                check_count INTEGER NOT NULL DEFAULT 1
            )
        """)
        execute(c, """
            INSERT INTO cloud_runtime_checks
                (marker_key, first_seen_utc, last_seen_utc, check_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT (marker_key) DO UPDATE SET
                last_seen_utc = EXCLUDED.last_seen_utc,
                check_count = cloud_runtime_checks.check_count + 1
        """, (MARKER_KEY, now, now))
        row = execute(c, """
            SELECT marker_key, first_seen_utc, last_seen_utc, check_count
            FROM cloud_runtime_checks
            WHERE marker_key = ?
        """, (MARKER_KEY,)).fetchone()

    return {
        "status": "ok",
        "database_backend": backend(),
        "marker_key": row[0],
        "first_seen_utc": row[1],
        "last_seen_utc": row[2],
        "check_count": row[3],
        "property_data_touched": False,
        "outreach_touched": False,
    }
