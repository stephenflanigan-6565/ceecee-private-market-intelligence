
#!/usr/bin/env python3
import os, json
from runtime_config import CFG, ADAPTERS
checks={
 "environment":CFG.environment,
 "database_configured":bool(CFG.database_url),
 "dry_run":CFG.dry_run,
 "outreach_enabled":CFG.outreach_enabled,
 "official_adapters_enabled":ADAPTERS["suffolk_official"] and ADAPTERS["southampton_official"],
 "paid_attom_active":ADAPTERS["attom"],
 "licensed_mls_active":ADAPTERS["mls"],
}
checks["safe_to_deploy_research"]=checks["database_configured"] and checks["official_adapters_enabled"] and CFG.dry_run and not CFG.outreach_enabled
print(json.dumps(checks,indent=2))
if not checks["safe_to_deploy_research"]:
    raise SystemExit("Research deployment safety check failed.")
