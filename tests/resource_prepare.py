"""Runs only in disposable CI network; no production credentials."""
import os,sqlite3,json,sys
from pathlib import Path
from resource_fixture import build,TARGETS
from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from pmi_drive_export_service import _bytes
root=Path('/results'); path=root/'fixture.sqlite'
if not path.exists(): build(path)
store=ReviewStore(os.environ['DATABASE_URL']); store.initialize(); ResearchStore(store.dsn).initialize()
src=sqlite3.connect(path); src.row_factory=sqlite3.Row
with store._session(write=True) as c:
 for table in TARGETS:
  c.execute('DELETE FROM '+table)
  rows=[dict(r) for r in src.execute('SELECT * FROM '+table)]; columns=list(rows[0])
  with c.cursor() as cur:
   cur.executemany('INSERT INTO '+table+' ('+','.join(columns)+') VALUES('+','.join('%s' for _ in columns)+')',[tuple(r[k] for k in columns) for r in rows])
src.close()
if '--reference' in sys.argv:
 snapshot=store.research_export_snapshot(); data=_bytes(snapshot); (root/'reference.json').write_bytes(data)
 report={'serialized_bytes':len(data),'cap_bytes':32*1024*1024,'fits':len(data)<=32*1024*1024,'counts':snapshot['manifest']['source_counts'],'review_counts':snapshot['review_counts']}
 (root/'reference-report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report))
