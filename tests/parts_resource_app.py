"""Full app, isolated disk-backed Google simulator shared by both workers."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from test_google_drive_client import FakeGoogle, Response
from pmi_google_drive import GoogleDriveClient
from pmi_drive_export_service import DriveExportService
from pmi_backup_parts import retrieve, restore
from pmi_review_store import ReviewStore
from pmi_research_store import ResearchStore
from test_exporter_interruption import ENV
from web_app import app
from flask import jsonify

ROOT=Path('/results'); REMOTE=ROOT/('remote-'+os.getenv('RESOURCE_MODE','parts')); REMOTE.mkdir(exist_ok=True)
def stage(name,**values):
 with (ROOT/'stages.jsonl').open('a') as f: f.write(json.dumps({'pid':os.getpid(),'stage':name,**values})+'\n')

class FileResponse:
 def __init__(self,path): self.path=path; self.status=200; self.headers={'Content-Length':str(path.stat().st_size)}
 def __enter__(self): self.f=self.path.open('rb'); return self
 def __exit__(self,*args): self.f.close()
 def read(self,n): return self.f.read(n)

class SharedDiskGoogle(FakeGoogle):
 def __init__(self): super().__init__(); self.lock=threading.Lock()
 def open(self,request,timeout):
  interrupt=False
  with self.lock, (REMOTE/'lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   path=REMOTE/'metadata.json'
   self.files=json.loads(path.read_text()) if path.exists() else {}
   url=urllib.parse.urlsplit(request.full_url); query=urllib.parse.parse_qs(url.query)
   if url.path.startswith('/upload/drive/v3/files'):
    raw=request.data; boundary=request.get_header('Content-type').split('boundary=',1)[1].encode()
    first=raw.index(b'\r\n\r\n')+4; end=raw.index(b'\r\n--'+boundary,first)
    meta=json.loads(raw[first:end]); start=raw.index(b'\r\n\r\n',end)+4; stop=raw.rindex(b'\r\n--'+boundary)
    key='file'+str(len(self.files)+1)
    with (REMOTE/key).open('wb') as f: f.write(memoryview(raw)[start:stop])
    meta.update(id=key,trashed=False,size=str(stop-start),owners=[{'permissionId':'principal123'}]); self.files[key]=meta
    stage('multipart',body_bytes=len(raw),content_bytes=stop-start,kind=meta['appProperties']['artifact_kind'])
    answer=Response({'id':key})
    if os.getenv('RESOURCE_MODE')=='parts-interrupt' and meta['appProperties']['artifact_kind']=='part-0002' and not (REMOTE/'interrupted.json').exists():
     interrupt=True
   elif query.get('alt')==['media']:
    answer=FileResponse(REMOTE/url.path.split('/')[4])
   else:
    answer=super().open(request,timeout); self.requests.clear()
   temporary=REMOTE/'metadata.tmp'; temporary.write_text(json.dumps(self.files)); temporary.replace(path)
  if interrupt:
   (REMOTE/'interrupted.json').write_text(json.dumps({'pid':os.getpid()})); stage('upload-awaiting-kill')
   time.sleep(70) # host kills this worker after remote persisted part, before acknowledgement
  return answer

fake=SharedDiskGoogle()
def client(): return GoogleDriveClient('synthetic','synthetic','synthetic',opener=fake)
@app.get('/_test/export')
def export():
 marker=REMOTE/'interrupted.json'
 clock=lambda: datetime.now(timezone.utc)+(timedelta(seconds=700) if marker.exists() else timedelta())
 service=DriveExportService(os.environ['DATABASE_URL'],environment=ENV,client_factory=client,clock=clock)
 stage('export-start')
 result=service.poll('synthetic-'+str(os.getpid()),force=True)
 stage('export-end',result=result,status=service.status())
 return jsonify(result)

@app.get('/_test/restore')
def restore_test():
 service=DriveExportService(os.environ['DATABASE_URL'],environment=ENV,client_factory=client)
 receipt=next(row for row in reversed(service._rows()) if row['kind']=='DRIVE_EXPORT_VERIFIED'); manifest_id=receipt['json_id']
 outcomes={}
 with tempfile.TemporaryDirectory() as spool:
  manifest=retrieve(client(),manifest_id,spool,expected_sha256=receipt['json_sha256'])
  for kind,dsn in [('sqlite',str(ROOT/('restored-'+os.getenv('RESOURCE_MODE','parts')+'.sqlite'))),('postgres',os.environ['RESTORE_DATABASE_URL'])]:
   dest=ReviewStore(dsn); dest.initialize(); ResearchStore(dsn).initialize()
   with dest._session(write=True) as c: dest._sql(c,'DELETE FROM pmi_research_control') # disposable bootstrap only
   counts=restore(dest,manifest,spool)
   # Exercise restored app-facing store reads without whole-snapshot construction.
   cases=dest.list_cases(); assert len(cases)==counts['pmi_review_cases']
   outcomes[kind]={'counts':counts,'every_record_reconciled':True,'source_revision':manifest['source_revision']}
 stage('restored',outcomes=outcomes,parts=len(manifest['parts']),serialized_bytes=manifest['serialized_bytes'])
 metadata=json.loads((REMOTE/'metadata.json').read_text())
 identities=[(v['appProperties'].get('export_id'),v['appProperties'].get('artifact_kind')) for v in metadata.values() if v.get('appProperties',{}).get('export_id')]
 assert len(identities)==len(set(identities))
 return jsonify(status='RESTORED',outcomes=outcomes,parts=len(manifest['parts']),serialized_bytes=manifest['serialized_bytes'],no_duplicate_artifacts=True)
