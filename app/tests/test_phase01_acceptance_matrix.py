import os
os.environ.setdefault("SUNNY_ADMIN_PASSWORD","phase01-test-secret-long")
from fastapi.testclient import TestClient
from backend.main import app
from backend import db, security

def test_matrix_is_protected_and_reports_real_blockers(tmp_path, monkeypatch):
    monkeypatch.setattr(db,"DB",tmp_path/"matrix.sqlite3")
    with TestClient(app) as client:
        assert client.get("/api/system/acceptance-matrix").status_code == 401
        r=client.post("/api/auth/login",json={"username":"admin","password":os.environ["SUNNY_ADMIN_PASSWORD"]})
        assert r.status_code==200
        headers={"Authorization":"Bearer "+r.json()["access_token"]}
        result=client.get("/api/system/acceptance-matrix",headers=headers)
        assert result.status_code==200
        data=result.json()
        assert data["status"]=="BLOCKED"
        assert data["api_method_paths"]>=128
        assert data["frontend"]["local_storage"] is True
        assert any(not item["verified"] for item in data["criteria"])
        assert len(data["blockers"])>=4
