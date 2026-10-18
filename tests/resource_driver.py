"""Host-side requests/metrics. Does not inflate the app container memory."""
import concurrent.futures,hashlib,json,subprocess,time,urllib.request,urllib.error,sys,threading,sqlite3
from pathlib import Path
from itsdangerous import URLSafeTimedSerializer
root=Path(sys.argv[1]); mode=sys.argv[2]; action=sys.argv[3]
ip=subprocess.check_output(['docker','inspect','pmi-resource-app','--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'],text=True).strip()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
signer=URLSafeTimedSerializer(hashlib.sha256(('PMI_OPERATOR_V1:'+'synthetic-review-key-at-least-24').encode()).hexdigest(),salt='pmi-review-session-v1')
cookie='pmi_review_operator='+signer.dumps({'actor':'PMI operator','nonce':'synthetic'})
with sqlite3.connect(root/'fixture.sqlite') as db: case_id=db.execute('SELECT case_id FROM pmi_review_cases ORDER BY case_id LIMIT 1').fetchone()[0]
case_path='/review/cases/'+case_id
def get(path,timeout=5):
 start=time.monotonic()
 try:
  req=urllib.request.Request('http://'+ip+':8080'+path,headers={'Cookie':cookie,'X-Forwarded-Proto':'https'})
  with opener.open(req,timeout=timeout) as r: raw=r.read(); code=r.status
  return {'path':path,'seconds':time.monotonic()-start,'code':code,'bytes':len(raw),'login_page':b'name="access_key"' in raw,'answer':json.loads(raw) if path.startswith('/_test') else None}
 except Exception as e: return {'path':path,'seconds':time.monotonic()-start,'error':type(e).__name__,'detail':str(e)}
deadline=time.monotonic()+35
while time.monotonic()<deadline:
 if get('/health',1).get('code')==200: break
 time.sleep(.5)
baseline=[get(p) for p in ['/health','/review/',case_path,'/about']*2]
print(subprocess.run(['docker','logs','--tail','40','pmi-resource-app'],capture_output=True,text=True).stderr,flush=True)
assert all(r.get('code')==200 and not r.get('login_page') for r in baseline), baseline
def metric():
 p=subprocess.run(['docker','exec','pmi-resource-app','sh','-c','cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events'],capture_output=True,text=True,timeout=5)
 return p.stdout
initial=metric(); responses=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 tasks=[pool.submit(get,'/_test/'+action,75) for _ in range(2 if action=='export' else 1)]
 deadline=time.monotonic()+75
 while time.monotonic()<deadline and not all(t.done() for t in tasks):
  responses.append(get(['/health','/review/',case_path][len(responses)%3],3)); time.sleep(.2)
 outcomes=[t.result() for t in tasks]
post=[]
for p in ['/health','/review/',case_path]*4:
 post.append(get(p)); time.sleep(.2)
final=metric()
report={'mode':mode,'action':action,'memory_limit_bytes':536870912,'baseline_metrics':initial,'final_metrics':final,'baseline_requests':baseline,'concurrent_requests':responses,'post_requests':post,'outcomes':outcomes}
root.joinpath('run-'+mode+'-'+action+'.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report))
