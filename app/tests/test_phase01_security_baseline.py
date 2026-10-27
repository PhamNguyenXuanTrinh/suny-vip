import os
os.environ.setdefault("SUNNY_ADMIN_PASSWORD","phase01-test-secret-long")
from fastapi.testclient import TestClient
from backend.main import app

def test_security_headers_and_health():
 with TestClient(app) as c:
  r=c.get('/api/health')
  assert r.status_code==200
  assert r.headers['x-content-type-options']=='nosniff'
  assert r.headers['x-frame-options']=='DENY'
  assert r.headers['referrer-policy']=='no-referrer'

def test_auth_rejects_invalid_bearer_format():
 with TestClient(app) as c:
  for header in ('fake-token','Basic Zm9vOmJhcg==','Bearer ','Bearer abc def'):
   r=c.get('/api/auth/me',headers={'Authorization':header})
   assert r.status_code==401,(header,r.text)

def test_auth_no_cache():
 with TestClient(app) as c:
  r=c.post('/api/auth/login',json={'username':'nonexistent','password':'bad'})
  assert r.headers['cache-control']=='no-store'
