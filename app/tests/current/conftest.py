from pathlib import Path
import uuid
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models import metadata as md
from backend.app.core.security import hash_password
from backend.scripts.create_admin import provision

PASSWORD='Test-password-long-2026!'

@pytest.fixture
def erp(tmp_path):
    cfg=Settings(tmp_path/'erp.sqlite3','test-secret-only-for-tests-'+str(uuid.uuid4()),tmp_path/'uploads')
    app=create_app(cfg)
    with TestClient(app) as client:
        a=provision(app.state.engine,'A','Tenant A','admin_a',PASSWORD,False)
        b=provision(app.state.engine,'B','Tenant B','admin_b',PASSWORD,False)
        def signin(name='admin_a'):
            r=client.post('/api/v1/auth/login',json={'username':name,'password':PASSWORD})
            assert r.status_code==200,r.text
            return {'Authorization':'Bearer '+r.json()['access_token']}
        yield client,signin,a,b

def add_user(client,organization_id,name,role='CTV',site_id=None,must_change=False):
    eid,uid=str(uuid.uuid4()),str(uuid.uuid4())
    with client.app.state.engine.begin() as c:
        c.execute(md.tables['employees'].insert().values(id=eid,organization_id=organization_id,employee_code=name,full_name=name,site_id=site_id))
        c.execute(md.tables['app_users'].insert().values(id=uid,organization_id=organization_id,employee_id=eid,username=name,password_hash=hash_password(PASSWORD),must_change_password=must_change))
        r=md.tables['roles'];rid=c.execute(sa.select(r.c.id).where(r.c.code==role,r.c.organization_id==organization_id)).scalar_one()
        c.execute(md.tables['user_roles'].insert().values(organization_id=organization_id,user_id=uid,role_id=rid,site_id=site_id))
    return uid,eid
