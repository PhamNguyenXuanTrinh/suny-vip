import os
os.environ.setdefault('SUNNY_ADMIN_PASSWORD','phase01-test-secret-long')
from fastapi.testclient import TestClient
from backend.main import app
from backend import db, security
import pytest

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db,"DB",tmp_path/"phase01.sqlite3")
    db.init()
    security.bootstrap()

def test_readiness_protected_and_reports_limits():
    with TestClient(app) as c:
        assert c.get('/api/system/readiness').status_code==401
        login=c.post('/api/auth/login',json={'username':'admin','password':os.environ['SUNNY_ADMIN_PASSWORD']})
        assert login.status_code==200,login.text
        headers={'Authorization':'Bearer '+login.json()['access_token']}
        r=c.get('/api/system/readiness',headers=headers)
        assert r.status_code==200,r.text
        data=r.json()
        assert data['checks']['database_integrity'] is True
        assert data['checks']['database_required_tables'] is True
        assert data['foundation_runtime_ready'] is True
        assert data['business_acceptance']=='NOT_VERIFIED'
        assert data['mobile_hardware_acceptance']=='NOT_VERIFIED'
        assert data['ui_api_binding_acceptance']=='NOT_VERIFIED'
        assert data['api_method_paths']>=126

def test_audit_summary_protected_and_bounded():
    with TestClient(app) as c:
        assert c.get('/api/system/audit-summary').status_code==401
        token=c.post('/api/auth/login',json={'username':'admin','password':os.environ['SUNNY_ADMIN_PASSWORD']}).json()['access_token']
        r=c.get('/api/system/audit-summary?limit=100000',headers={'Authorization':'Bearer '+token})
        assert r.status_code==200
        assert r.json()['limit']==100
        assert isinstance(r.json()['items'],list)
