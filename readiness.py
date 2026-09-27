
#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
r=subprocess.run([sys.executable,str(ROOT/"portability_audit.py")],capture_output=True,text=True)
state={"code_portability_static_check":"PASS" if r.returncode==0 else "REVIEW",
       "local_sqlite_integration":"PASS","postgres_integration":"NEXT_EXTERNAL_TEST",
       "live_source_collection":"AFTER_HOSTED_RUNTIME","outreach":"LOCKED_OFF",
       "audit":r.stdout.strip()}
print(json.dumps(state,indent=2))
if r.returncode: raise SystemExit(2)
