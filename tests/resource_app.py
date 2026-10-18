"""Test-only full-app entrypoint. No production imports are modified on disk."""
import os,json,urllib.parse,time
from pathlib import Path
from test_google_drive_client import FakeGoogle,Response
from pmi_google_drive import GoogleDriveClient
from pmi_drive_export_service import DriveExportService
from test_exporter_interruption import ENV

ROOT=Path('/results')
def stage(name,**fields):
 with (ROOT/'stages.jsonl').open('a') as f: f.write(json.dumps({'pid':os.getpid(),'stage':name,**fields})+'\n')
class FileResponse:
 def __init__(self,path): self.path=path; self.status=200; self.headers={'Content-Length':str(path.stat().st_size)}
 def __enter__(self): self.f=self.path.open('rb'); return self
 def __exit__(self,*args): self.f.close()
 def read(self,n): return self.f.read(n)
class DiskGoogle(FakeGoogle):
 def open(self,request,timeout):
  parts=urllib.parse.urlsplit(request.full_url); query=urllib.parse.parse_qs(parts.query)
  if parts.path.startswith('/upload/drive/v3/files'):
   raw=request.data; boundary=request.get_header('Content-type').split('boundary=',1)[1].encode()
   first=raw.index(b'\r\n\r\n')+4; end=raw.index(b'\r\n--'+boundary,first)
   meta=json.loads(raw[first:end]); start=raw.index(b'\r\n\r\n',end)+4; stop=raw.rindex(b'\r\n--'+boundary)
   key='file'+str(len(self.files)+1); path=ROOT/key
   with path.open('wb') as f: f.write(memoryview(raw)[start:stop])
   meta.update(id=key,trashed=False,size=str(stop-start),owners=[{'permissionId':'principal123'}]); self.files[key]=meta
   stage('multipart',body_bytes=len(raw),content_bytes=stop-start)
   return Response({'id':key})
  if query.get('alt')==['media']:
   stage('readback',file_id=parts.path.split('/')[4]); return FileResponse(ROOT/parts.path.split('/')[4])
  answer=super().open(request,timeout); self.requests.clear(); return answer

if os.getenv('RESOURCE_MODE')=='raised-cap':
 import pmi_google_drive
 pmi_google_drive.MAX_ARTIFACT_BYTES=128*1024*1024 # isolated counterfactual, NOT a proposed safe fix
from web_app import app
from flask import jsonify
fake=DiskGoogle()
client=lambda:GoogleDriveClient('synthetic-client','synthetic-secret','synthetic-refresh',opener=fake)
@app.get('/_test/export')
def export():
 stage('export-start')
 service=DriveExportService(os.environ['DATABASE_URL'],environment=ENV,client_factory=client)
 original=service.store.research_export_snapshot
 def snapshot():
  stage('snapshot-start'); result=original(); stage('snapshot-complete'); return result
 service.store.research_export_snapshot=snapshot
 answer=service.poll('synthetic-'+str(os.getpid())); stage('export-end',result=answer,status=service.status())
 return jsonify(answer)
@app.get('/_test/multipart')
def multipart():
 import hashlib
 c=client(); folder=c.ensure_private_folder(); data=(ROOT/'reference.json').read_bytes()
 stage('multipart-start',serialized_bytes=len(data))
 try:
  uploaded=c.upload(folder['id'],'synthetic.json','application/json',data,'synthetic-reference','json')
  restored=c.download(uploaded['id']); assert hashlib.sha256(data).digest()==hashlib.sha256(restored).digest()
  stage('multipart-verified',bytes=len(restored)); return jsonify(status='VERIFIED',bytes=len(restored))
 except Exception as e:
  stage('multipart-failed',error=getattr(e,'code',type(e).__name__)); return jsonify(status='FAILED',error=getattr(e,'code',type(e).__name__))
