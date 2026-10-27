from pathlib import Path
from backend.main import app

def test_foundation_endpoints_exist():
    paths={getattr(r,"path","") for r in app.routes}
    assert {"/api/system/status","/api/system/roles","/api/system/api-catalog"} <= paths

def test_v86_files_are_preserved():
    root=Path(__file__).resolve().parents[1]
    assert (root/"public/v86.html").is_file()
    assert (root/"public/index.html").is_file()
    assert (root/"public/app.html").is_file()

def test_system_routes_require_authentication():
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        for route in ("/api/system/status","/api/system/roles","/api/system/api-catalog"):
            assert client.get(route).status_code==401
