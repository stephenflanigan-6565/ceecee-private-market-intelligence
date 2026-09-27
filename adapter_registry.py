
#!/usr/bin/env python3
from db import connect
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from runtime_config import ADAPTERS

ROOT=Path(__file__).resolve().parent
DB=ROOT/"ceecee.db"

META = {
 "suffolk_official": ("PUBLIC_RECORD","0","0","Official parcel/owner/transfer/party/lineage rails"),
 "southampton_official": ("PUBLIC_RECORD","0","0","Official zoning/building/property context"),
 "assessment_history": ("PUBLIC_RECORD","0","0","Annual roll history"),
 "attom": ("COMMERCIAL_ENRICHMENT","1","1","Optional enrichment; dormant without API key"),
 "mls": ("LICENSED_MARKET_DATA","1","1","Optional licensed listing/market-history feed"),
 "legacy_ceecee": ("PROPRIETARY","0","0","CeeCee historical CRM/spreadsheet imports"),
 "buyer_demand": ("FIRST_PARTY","0","0","Genuine buyer requirement book"),
}
def main():
    c=connect(); c.executescript((ROOT/"schema.sql").read_text())
    now=datetime.now(timezone.utc).isoformat()
    for k, enabled in ADAPTERS.items():
        cat, cred, paid, notes=META[k]
        c.execute("""insert into adapter_registry(adapter_key,category,enabled,credential_required,paid,status,last_checked_at,notes)
        values(?,?,?,?,?,'AVAILABLE',?,?)
        on conflict(adapter_key) do update set enabled=excluded.enabled,last_checked_at=excluded.last_checked_at,notes=excluded.notes""",
        (k,cat,int(enabled),int(cred),int(paid),now,notes))
    c.commit()
    for row in c.execute("select adapter_key,category,enabled,paid,status from adapter_registry order by adapter_key"):
        print(row)
    c.close()
if __name__=="__main__": main()
