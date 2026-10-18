"""Bounded, versioned full-research backup. No network while DB snapshot is open.

Parts are <=4 MiB, records <=1 MiB before encoding (encoded line <=4 MiB).
Existing 32 MiB client upload/readback cap remains unchanged. Oversized rows,
disk failures and malformed packages fail explicitly; no truncation occurs.
"""
import hashlib
import json
import os
from pathlib import Path

from pmi_research_export import without_secrets

VERSION = 'PMI_RESEARCH_PARTS_V2'
PART_BYTES = 4 * 1024 * 1024
ROW_BYTES = 1024 * 1024
MAX_PARTS = 4096  # explicit 16 GiB package ceiling, never silently trim
TABLES = {
 'pmi_review_imports': 'import_id payload_json summary_json actor recorded_at',
 'pmi_review_cases': 'case_id version_id state pilot import_id updated_at',
 'pmi_review_case_versions': 'version_id case_id data_json recorded_at',
 'pmi_review_events': 'event_id case_id kind data_json recorded_at',
 'pmi_ai_review_records': 'record_key kind case_id analysis_id data_json recorded_at',
 'pmi_research_control': 'control_id enabled lease_run_id lease_token lease_until actor updated_at',
 'pmi_research_schedule': 'case_id parcel_id next_due_at requested last_attempt_at last_completed_at',
 'pmi_research_runs': 'run_id case_id parcel_id case_json worker_id lease_token started_at completed_at status bundle_json',
 'pmi_research_snapshots': 'snapshot_id case_id parcel_id source_key content_hash source_json first_checked_at',
 'pmi_research_sources': 'case_id source_key snapshot_id checked_at source_json',
}
TABLES = {t: c.split() for t, c in TABLES.items()}
EXCLUSIONS = {'memory_kind_prefix': 'DRIVE_EXPORT_',
 'credential_fields': 'existing without_secrets policy',
 'lease_token_and_worker_id': 'empty or null; never restored as active capability'}

def encoded(value):
 return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def sha(data):
 return hashlib.sha256(data).hexdigest()

def condition(table):
 return " WHERE SUBSTR(kind,1,13)<>'DRIVE_EXPORT_'" if table == 'pmi_ai_review_records' else ''

def normalized(columns, row):
 output = list(row)
 for i, col in enumerate(columns):
  value = output[i]
  if col in {'worker_id', 'lease_token'}:
   output[i] = '' if value is not None else None
  elif col.endswith('_json') and value is not None:
   parsed = json.loads(value)
   clean = without_secrets(parsed)
   # Preserve exact original JSON text if no credential field was removed.
   if clean != parsed: output[i] = encoded(clean).decode('utf-8')
 return output

def rows(store, connection, table):
 columns = TABLES[table]
 # Check before libpq/SQLite fetches a potentially unbounded record.
 length = 'octet_length' if store.postgres else 'length'
 terms = [f'COALESCE({length}(CAST({c} AS '+('TEXT' if store.postgres else 'BLOB')+')),0)' for c in columns]
 largest = store._sql(connection, 'SELECT COALESCE(max('+ '+'.join(terms)+'),0) FROM '+table+condition(table)).fetchone()[0]
 if largest > ROW_BYTES: raise ValueError('backup_record_too_large')
 order = 'case_id,source_key' if table == 'pmi_research_sources' else columns[0]
 sql = 'SELECT '+','.join(columns)+' FROM '+table+condition(table)+' ORDER BY '+order
 cursor = connection.cursor(name='backup_'+table) if store.postgres else connection.cursor()
 try:
  cursor.execute(sql)
  while True:
   row = cursor.fetchone()
   if row is None: break
   yield normalized(columns, row)
 finally: cursor.close()

def build_package(store, directory):
 directory = Path(directory)
 manifest = {'version': VERSION, 'complete': True, 'tables': {}, 'parts': [], 'exclusions': EXCLUSIONS}
 buffer = bytearray()
 def flush():
  if not buffer: return
  index = len(manifest['parts'])
  if index >= MAX_PARTS: raise ValueError('backup_package_too_large')
  path = directory / ('part-%04d.jsonl' % index)
  with path.open('xb') as stream:
   stream.write(buffer); stream.flush(); os.fsync(stream.fileno())
  manifest['parts'].append({'index': index, 'bytes': len(buffer), 'sha256': sha(buffer)})
  buffer.clear()
 with store._session(snapshot=True) as connection:
  if store.postgres:
   connection.execute("SET LOCAL statement_timeout='60s'")
   connection.execute("SET LOCAL lock_timeout='500ms'")
  for table, columns in TABLES.items():
   expected = store._sql(connection, 'SELECT count(*) FROM '+table+condition(table)).fetchone()[0]
   digest = hashlib.sha256(); count = 0
   for row in rows(store, connection, table):
    line = encoded([table, row]) + b'\n'
    if len(line) > PART_BYTES: raise ValueError('backup_encoded_record_too_large')
    if len(buffer) + len(line) > PART_BYTES: flush()
    buffer.extend(line); digest.update(line); count += 1
   if count != expected: raise ValueError('backup_snapshot_count_mismatch')
   manifest['tables'][table] = {'columns': columns, 'count': count, 'sha256': digest.hexdigest()}
 flush()
 manifest['source_revision'] = sha(encoded(manifest['tables']))
 manifest['serialized_bytes'] = sum(p['bytes'] for p in manifest['parts'])
 return manifest

def validate_manifest(manifest):
 if manifest.get('version') != VERSION or manifest.get('complete') is not True or manifest.get('exclusions') != EXCLUSIONS:
  raise ValueError('invalid_backup_manifest')
 if set(manifest['tables']) != set(TABLES) or len(manifest['parts']) > MAX_PARTS:
  raise ValueError('invalid_backup_tables')
 for table, columns in TABLES.items():
  entry = manifest['tables'][table]
  if entry['columns'] != columns or type(entry['count']) is not int or entry['count'] < 0:
   raise ValueError('invalid_backup_schema')
 if manifest['source_revision'] != sha(encoded(manifest['tables'])):
  raise ValueError('invalid_backup_revision')
 for i, part in enumerate(manifest['parts']):
  if part['index'] != i or type(part['bytes']) is not int or not 0 < part['bytes'] <= PART_BYTES:
   raise ValueError('invalid_backup_part')
 if manifest['serialized_bytes'] != sum(p['bytes'] for p in manifest['parts']):
  raise ValueError('invalid_backup_size')

def verify_parts(manifest, directory):
 validate_manifest(manifest)
 counts = {t: 0 for t in TABLES}; hashes = {t: hashlib.sha256() for t in TABLES}
 for part in manifest['parts']:
  path = Path(directory) / ('part-%04d.jsonl' % part['index'])
  if path.stat().st_size != part['bytes']: raise ValueError('backup_part_size_mismatch')
  with path.open('rb') as stream:
   digest = hashlib.sha256()
   while True:
    line = stream.readline(PART_BYTES + 1)
    if not line: break
    if len(line) > PART_BYTES or not line.endswith(b'\n'): raise ValueError('invalid_backup_record')
    table, row = json.loads(line)
    if table not in TABLES or not isinstance(row, list) or len(row) != len(TABLES[table]) or encoded([table,row])+b'\n' != line:
     raise ValueError('invalid_backup_record')
    if any(v is not None and type(v) not in (str, int) for v in row): raise ValueError('invalid_backup_value')
    digest.update(line); hashes[table].update(line); counts[table] += 1
   if digest.hexdigest() != part['sha256']: raise ValueError('backup_part_hash_mismatch')
 for table in TABLES:
  if counts[table] != manifest['tables'][table]['count'] or hashes[table].hexdigest() != manifest['tables'][table]['sha256']:
   raise ValueError('backup_table_mismatch')
 return counts

def deliver(client, folder_id, manifest, directory, export_id):
 """Part identities survive interrupted requests; manifest is uploaded last."""
 verify_parts(manifest, directory)
 for part in manifest['parts']:
  path = Path(directory) / ('part-%04d.jsonl' % part['index'])
  data = path.read_bytes()  # one <=4 MiB part, never the full backup
  uploaded = client.upload(folder_id, path.name, 'application/x-ndjson', data, export_id, 'part-%04d' % part['index'])
  readback = client.download(uploaded['id'])
  if len(readback) != part['bytes'] or sha(readback) != part['sha256']:
   raise ValueError('backup_readback_mismatch')
  part['file_id'] = uploaded['id']
  del data, readback
 content = encoded(manifest)
 if len(content) > 1024*1024: raise ValueError('backup_manifest_too_large')
 result = client.upload(folder_id, 'PMI-'+manifest['source_revision'][:12]+'-manifest.json', 'application/json', content, export_id, 'manifest')
 if client.download(result['id']) != content: raise ValueError('backup_manifest_readback_mismatch')
 return result

def retrieve(client, manifest_id, directory):
 """Retrieve and reconcile remote records without trusting local spool files."""
 raw = client.download(manifest_id)
 if len(raw) > 1024*1024: raise ValueError('backup_manifest_too_large')
 manifest = json.loads(raw); validate_manifest(manifest)
 for part in manifest['parts']:
  content = client.download(part['file_id'])
  if len(content) != part['bytes'] or sha(content) != part['sha256']: raise ValueError('backup_readback_mismatch')
  with (Path(directory)/('part-%04d.jsonl' % part['index'])).open('xb') as stream:
   stream.write(content)
  del content
 verify_parts(manifest, directory)
 return manifest

def restore(store, manifest, directory):
 """Explicit offline restore into an initialized EMPTY database, atomic DML.

No schema creation, replacement, deletes or overwrite of existing research.
Callers must keep the destination app/schedulers stopped during restore.
"""
 verify_parts(manifest, directory)
 with store._session(write=True) as connection:
  for table in TABLES:
   if store._sql(connection, 'SELECT count(*) FROM '+table).fetchone()[0]:
    raise ValueError('restore_requires_empty_database')
  for part in manifest['parts']:
   with (Path(directory)/('part-%04d.jsonl' % part['index'])).open('rb') as stream:
    for line in stream:
     table, row = json.loads(line)
     columns = TABLES[table]
     store._sql(connection, 'INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')', row)
  # Reconcile every restored record and column before committing.
  for table in TABLES:
   digest = hashlib.sha256(); count = 0
   for row in rows(store, connection, table):
    digest.update(encoded([table,row])+b'\n'); count += 1
   if count != manifest['tables'][table]['count'] or digest.hexdigest() != manifest['tables'][table]['sha256']:
    raise ValueError('restore_reconciliation_failed')
 return {t: manifest['tables'][t]['count'] for t in TABLES}
