
#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
issues=[]
for p in ROOT.glob("*.py"):
    if p.name in {"db.py","portability_audit.py","readiness.py"}: continue
    s=p.read_text()
    if "sqlite3.connect(" in s: issues.append((p.name,"hard-coded sqlite connection"))
    if ".lastrowid" in s: issues.append((p.name,"direct backend-specific insert id"))
print("PORTABILITY AUDIT")
if issues:
    for x in issues: print("REVIEW:",*x)
    raise SystemExit(2)
print("PASS: no hard-coded SQLite connections or direct lastrowid usage in operating modules")
