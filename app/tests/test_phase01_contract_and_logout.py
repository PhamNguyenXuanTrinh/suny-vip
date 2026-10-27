import os
os.environ.setdefault('SUNNY_ADMIN_PASSWORD','phase01-test-secret-long')
from fastapi.testclient import TestClient
from backend.main import app
from backend import security
from backend.db import transaction
import uuid

def auth_header(client):
 username="test_"+uuid.uuid4().hex[:16]
 password="safe-test-password-123"
 with transaction() as conn:
  conn.execute("INSERT INTO api_accounts VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,username,security.hash_password(password),"director",None,security.now()))
 response=client.post("/api/auth/login",json={"username":username,"password":password})
 assert response.status_code==200,response.text
 return {"Authorization":"Bearer "+response.json()["access_token"]}

def test_phase01_ui_contract_truthful():
 with TestClient(app) as c:
  h=auth_header(c)
  result=c.get('/api/system/ui-contract',headers=h)
  assert result.status_code==200
  data=result.json()
  assert data['ui_uses_browser_local_storage'] is True
  assert data['ui_calls_backend_fetch'] is False
  assert data['acceptance']=='BLOCKED'

def test_logout_revokes_token():
 with TestClient(app) as c:
  h=auth_header(c)
  assert c.get('/api/auth/me',headers=h).status_code==200
  assert c.post('/api/auth/logout',headers=h).json()['revoked'] is True
  assert c.get('/api/auth/me',headers=h).status_code==401
