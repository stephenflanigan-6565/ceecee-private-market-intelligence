import contextlib
import io
import json
import unittest
import urllib.error
from pmi_drive_auth_diagnostic import diagnose, ERROR_BODY_LIMIT
from pmi_google_drive import ENV_NAMES, DRIVE_SCOPE

SECRET = 'PRIVATE_SENTINEL_credential_header_body_account'
ENV = dict(zip(ENV_NAMES, [SECRET+'id', SECRET+'secret', SECRET+'refresh']))

class Response:
    def __init__(self, body): self.body=json.dumps(body).encode(); self.status=200; self.headers={}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n): return self.body[:n]

class ErrorBody(io.BytesIO):
    def read(self,n=-1):
        assert 0 <= n <= ERROR_BODY_LIMIT+1
        return super().read(n)

class Fake:
    def __init__(self, stage=None, body=None, status=400, transport=False):
        self.stage=stage; self.body=body; self.status=status; self.transport=transport; self.calls=[]; self.stream=None
    def open(self,request,timeout):
        self.calls.append(request.full_url)
        stage='token_refresh' if request.full_url.endswith('/token') else 'drive_identity'
        if stage==self.stage:
            if self.transport: raise RuntimeError(SECRET)
            raw=self.body if isinstance(self.body,bytes) else json.dumps(self.body).encode()
            self.stream=ErrorBody(raw)
            raise urllib.error.HTTPError(request.full_url,self.status,SECRET,{'Authorization':SECRET},self.stream)
        return Response({'access_token':SECRET,'token_type':'Bearer','scope':DRIVE_SCOPE,'expires_in':3600}
            if stage=='token_refresh' else {'user':{'permissionId':SECRET}})

class DiagnosticTests(unittest.TestCase):
    def run_safe(self,fake):
        out=io.StringIO(); err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err): result=diagnose(ENV,opener=fake)
        self.assertEqual(set(result),{'stage','error_identifier','http_status'})
        self.assertNotIn(SECRET,json.dumps(result)+out.getvalue()+err.getvalue())
        self.assertEqual(out.getvalue()+err.getvalue(),'')
        if fake.stream is not None: self.assertTrue(fake.stream.closed)
        return result
    def test_token_failure_stops_before_drive(self):
        f=Fake('token_refresh',{'error':'invalid_grant','error_description':SECRET,'access_token':SECRET})
        self.assertEqual(self.run_safe(f),{'stage':'token_refresh','error_identifier':'invalid_grant','http_status':400})
        self.assertEqual(len(f.calls),1)
    def test_identity_failure_is_distinct(self):
        f=Fake('drive_identity',{'error':{'status':'PERMISSION_DENIED','message':SECRET}},403)
        self.assertEqual(self.run_safe(f),{'stage':'drive_identity','error_identifier':'PERMISSION_DENIED','http_status':403})
        self.assertEqual(len(f.calls),2)
    def test_success_discards_token_and_account(self):
        f=Fake(); self.assertEqual(self.run_safe(f),{'stage':'drive_identity','error_identifier':None,'http_status':200})
        self.assertEqual(len(f.calls),2)
        self.assertTrue(f.calls[1].startswith('https://www.googleapis.com/drive/v3/about?'))
    def test_unknown_malformed_oversized_and_secret_codes(self):
        for body in [{'error':SECRET}, {'error_description':SECRET}, b'bad json '+SECRET.encode(), b'x'*(ERROR_BODY_LIMIT+2), {'error':['invalid_grant']}, {'error':{'errors':SECRET}}]:
            with self.subTest(body_type=type(body).__name__):
                self.assertEqual(self.run_safe(Fake('token_refresh',body))['error_identifier'],'provider_error_unclassified')
    def test_drive_reason_allowlist(self):
        self.assertEqual(self.run_safe(Fake('drive_identity',{'error':{'errors':[{'reason':'insufficientPermissions','message':SECRET}]}},403))['error_identifier'],'insufficientPermissions')
    def test_transport_failure_is_sanitized(self):
        self.assertEqual(self.run_safe(Fake('token_refresh',transport=True))['error_identifier'],'drive_transport_error')
    def test_missing_config_performs_no_request(self):
        f=Fake(); result=diagnose({},opener=f)
        self.assertEqual(result['error_identifier'],'drive_credentials_missing'); self.assertEqual(f.calls,[])

if __name__=='__main__': unittest.main()
