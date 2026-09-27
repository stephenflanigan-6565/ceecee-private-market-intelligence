
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class RuntimeConfig:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///ceecee.db")
    environment: str = os.getenv("CEECEE_ENV", "development")
    dry_run: bool = os.getenv("CEECEE_DRY_RUN", "1") != "0"
    outreach_enabled: bool = os.getenv("CEECEE_OUTREACH_ENABLED", "0") == "1"
    max_retries: int = int(os.getenv("CEECEE_MAX_RETRIES", "3"))

CFG = RuntimeConfig()

# Paid / licensed adapters remain dormant until credentials are intentionally supplied.
ADAPTERS = {
    "suffolk_official": os.getenv("ADAPTER_SUFFOLK_OFFICIAL", "1") == "1",
    "southampton_official": os.getenv("ADAPTER_SOUTHAMPTON_OFFICIAL", "1") == "1",
    "assessment_history": os.getenv("ADAPTER_ASSESSMENT_HISTORY", "1") == "1",
    "attom": bool(os.getenv("ATTOM_API_KEY")),
    "mls": bool(os.getenv("MLS_FEED_TOKEN")),
    "legacy_ceecee": os.getenv("ADAPTER_LEGACY_CEECEE", "1") == "1",
    "buyer_demand": os.getenv("ADAPTER_BUYER_DEMAND", "1") == "1",
}
