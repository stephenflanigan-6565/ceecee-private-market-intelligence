"""Conservative retained-payload budget; no snapshot or record contents read.

This protects the materializing exporter. It is NOT a serialized-size prediction
or a streaming backup implementation. Rejection preserves all research history.
"""
from pmi_google_drive import DriveError

MAX_RETAINED_PAYLOAD_BYTES = 32 * 1024 * 1024
PAYLOADS = (
 ('pmi_review_imports', ('payload_json','summary_json')),
 ('pmi_review_case_versions', ('data_json',)),
 ('pmi_review_events', ('data_json',)),
 ('pmi_ai_review_records', ('data_json',)),
 ('pmi_research_runs', ('case_json','bundle_json')),
 ('pmi_research_snapshots', ('source_json',)),
 ('pmi_research_sources', ('source_json',)),
)
def check_retained_payload_budget(store):
 with store._session(snapshot=True) as connection:
  if store.postgres:
   connection.execute("SET LOCAL statement_timeout='10s'")
   connection.execute("SET LOCAL lock_timeout='500ms'")
   connection.execute("SET LOCAL max_parallel_workers_per_gather=0")
  selects=[]
  for table,columns in PAYLOADS:
   terms=[('COALESCE(octet_length('+c+'),0)::bigint' if store.postgres else 'COALESCE(length(CAST('+c+' AS BLOB)),0)') for c in columns]
   where=" WHERE SUBSTR(kind,1,13)<>'DRIVE_EXPORT_'" if table=='pmi_ai_review_records' else ''
   selects.append('SELECT COALESCE(sum('+ '+'.join(terms)+'),0) AS bytes FROM '+table+where)
  total=int(store._sql(connection,'SELECT sum(bytes) FROM ('+' UNION ALL '.join(selects)+') AS retained').fetchone()[0])
 if total>MAX_RETAINED_PAYLOAD_BYTES:
  raise DriveError('retained_payload_budget_exceeded')
 return total
