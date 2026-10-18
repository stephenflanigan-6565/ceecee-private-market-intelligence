"""Synthetic only: reproduce measured counts/JSON bytes, never production content."""
import copy, json, sqlite3, os
from pathlib import Path
from test_exporter_interruption import InterruptionSQLite
from test_research_store import pilot_payload

TARGETS = {
 'pmi_review_imports': (8,3215808,401976,['payload_json','summary_json']),
 'pmi_review_cases': (194,0,0,[]),
 'pmi_review_case_versions': (1559,68917969,56722,['data_json']),
 'pmi_review_events': (1655,350580,1042,['data_json']),
 'pmi_ai_review_records': (1592,21922848,292177,['data_json']),
 'pmi_research_control': (1,0,0,[]),
 'pmi_research_schedule': (5,0,0,[]),
 'pmi_research_runs': (54,855066,16447,['case_json','bundle_json']),
 'pmi_research_snapshots': (20,62054,6273,['source_json']),
 'pmi_research_sources': (20,62394,6290,['source_json']),
}
def encode(v): return json.dumps(v,ensure_ascii=False,separators=(',',':'))
def size(row,cols): return sum(len((row[c] or '').encode()) for c in cols)
def pad(rows,cols,total,maximum,eligible=None):
 eligible=list(range(len(rows))) if eligible is None else eligible
 for i in eligible:
  col=cols[-1]; doc=json.loads(rows[i][col] or '{}'); doc['_synthetic_padding']=''; rows[i][col]=encode(doc)
 assert max(size(r,cols) for r in rows)<=maximum, (maximum,max(size(r,cols) for r in rows))
 # Ensure the measured maximum, then distribute exact remaining bytes.
 chosen=max(eligible,key=lambda i:size(rows[i],cols))
 additions={chosen:maximum-size(rows[chosen],cols)}
 remaining=total-sum(size(r,cols) for r in rows)-additions[chosen]
 assert remaining>=0, (total,remaining)
 for i in eligible:
  if i==chosen: continue
  n=min(remaining,maximum-size(rows[i],cols)); additions[i]=n; remaining-=n
 assert remaining==0, remaining
 for i,n in additions.items():
  col=cols[-1]; doc=json.loads(rows[i][col]); doc['_synthetic_padding']='x'*n; rows[i][col]=encode(doc)
 assert sum(size(r,cols) for r in rows)==total
 assert max(size(r,cols) for r in rows)==maximum

def build(path):
 fixture=InterruptionSQLite(); fixture.setUp()
 fixture.store.import_payload(pilot_payload(194),'synthetic-operator')
 src=sqlite3.connect(fixture.dsn); src.row_factory=sqlite3.Row
 data={t:[dict(r) for r in src.execute('SELECT * FROM '+t)] for t in TARGETS}
 cases=data['pmi_review_cases']; caseids=[r['case_id'] for r in cases]
 versions={r['version_id']:r for r in data['pmi_review_case_versions']}
 for table,(count,total,maximum,cols) in TARGETS.items():
  rows=data[table]
  if table=='pmi_research_sources':
   # One pointer per synthetic retained snapshot; unique source keys preserve all originals.
   snaps=data['pmi_research_snapshots']
   pointed={r['snapshot_id'] for r in rows}
   for snap in snaps:
    if snap['snapshot_id'] not in pointed and any(r['source_key']==snap['source_key'] and r['case_id']==snap['case_id'] for r in rows):
     snap['source_key']='synthetic-historical-'+snap['snapshot_id'][:12]
   for snap in snaps:
    if any(r['snapshot_id']==snap['snapshot_id'] for r in rows): continue
    rows.append({'case_id':snap['case_id'],'source_key':snap['source_key'],'snapshot_id':snap['snapshot_id'],'checked_at':snap['first_checked_at'],'source_json':snap['source_json']})
  while len(rows)<count:
   n=len(rows); r=copy.deepcopy(rows[0])
   if table=='pmi_review_imports': r['import_id']='synthetic-import-'+str(n)
   elif table=='pmi_review_case_versions': r=copy.deepcopy(versions[cases[n%194]['version_id']]); r['version_id']='synthetic-version-'+str(n)
   elif table=='pmi_review_events': r.update(event_id='synthetic-note-'+str(n),case_id=caseids[n%194],kind='STATE',data_json=encode({'state':'NEW','note':'Synthetic retained note'}))
   elif table=='pmi_ai_review_records': r.update(record_key='synthetic-memory-'+str(n),kind='PATTERN',case_id=caseids[n%194],analysis_id='',data_json=encode({'synthetic':True}))
   elif table=='pmi_research_schedule':
    r['case_id']=caseids[n]; r['parcel_id']=json.loads(versions[cases[n]['version_id']]['data_json'])['baseline']['parcel_id']
   elif table=='pmi_research_runs': r['run_id']='synthetic-run-'+str(n)
   elif table=='pmi_research_snapshots': r.update(snapshot_id='synthetic-snapshot-'+str(n),source_key='synthetic-source-'+str(n))
   else: raise AssertionError(table)
   rows.append(r)
  assert len(rows)==count,(table,len(rows),count)
  if cols:
   eligible=[i for i,r in enumerate(rows) if not (table=='pmi_review_events' and r['kind']=='REVIEW') and not (table=='pmi_ai_review_records' and r['kind']=='FEEDBACK')]
   if table=='pmi_review_case_versions':
    current={r['version_id'] for r in cases}; a=[r for r in rows if r['version_id'] in current]; b=[r for r in rows if r['version_id'] not in current]
    pad(a,cols,8576449,56722); pad(b,cols,total-8576449,56722)
   else: pad(rows,cols,total,maximum,eligible)
 # All original corrected evidence/reviews remain; pointers refer to valid synthetic sources.
 dest=sqlite3.connect(path)
 for (statement,) in src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name LIKE 'pmi_%'"):
  dest.execute(statement)
 for t,rows in data.items():
  cols=list(rows[0]); dest.executemany('INSERT INTO '+t+' ('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',[tuple(r[c] for c in cols) for r in rows])
 dest.commit(); dest.close(); src.close()
 manifest={t:[len(rows),sum(size(r,TARGETS[t][3]) for r in rows),max(size(r,TARGETS[t][3]) for r in rows)] for t,rows in data.items()}
 Path(str(path)+'.counts.json').write_text(json.dumps(manifest,indent=2))
 return manifest

if __name__=='__main__':
 import sys
 print(json.dumps(build(sys.argv[1]),indent=2))
