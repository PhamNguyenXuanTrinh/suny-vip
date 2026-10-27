import sqlalchemy as sa
from backend.app.models import metadata as md
from .conftest import PASSWORD,add_user

def test_auth_tenant_boundaries_secrets_and_role_revoke(erp):
    c,login,a,b=erp;h=login()
    assert c.get('/api/v1/users').status_code==401
    data=c.get('/api/v1/users',headers=h).json()
    assert len(data['items'])==1 and data['items'][0]['username']=='admin_a'
    assert 'password_hash' not in str(data)
    assert c.patch('/api/v1/users/'+b['user_id'],headers=h,json={'is_active':False}).status_code==404
    uid,eid=add_user(c,a['organization_id'],'sales','SALES')
    sh=login('sales')
    assert c.get('/api/v1/users',headers=sh).status_code==403
    assert c.post('/api/v1/users/'+uid+'/roles',headers=h,json={'grants':[{'code':'ADMIN'}]}).status_code==200
    assert c.get('/api/v1/users',headers=sh).status_code==200
    assert c.post('/api/v1/users/'+uid+'/roles',headers=h,json={'grants':[]}).status_code==200
    assert c.get('/api/v1/users',headers=sh).status_code==403

def test_refresh_rotation_reuse_revokes_family_and_logout(erp):
    c,login,a,b=erp
    tokens=c.post('/api/v1/auth/login',json={'username':'admin_a','password':PASSWORD}).json()
    second=c.post('/api/v1/auth/refresh',json={'refresh_token':tokens['refresh_token']})
    assert second.status_code==200
    h={'Authorization':'Bearer '+tokens['access_token']}
    assert c.get('/api/v1/auth/me',headers=h).status_code==401
    h2={'Authorization':'Bearer '+second.json()['access_token']}
    assert c.get('/api/v1/auth/me',headers=h2).status_code==200
    assert c.post('/api/v1/auth/refresh',json={'refresh_token':tokens['refresh_token']}).status_code==401
    assert c.get('/api/v1/auth/me',headers=h2).status_code==401
    h=login();assert c.post('/api/v1/auth/logout',headers=h).status_code==200
    assert c.get('/api/v1/auth/me',headers=h).status_code==401

def test_forced_password_change_and_disabled_org(erp):
    c,login,a,b=erp
    uid,eid=add_user(c,a['organization_id'],'new_admin','ADMIN',must_change=True)
    h=login('new_admin')
    assert c.get('/api/v1/auth/me',headers=h).json()['must_change_password'] is True
    assert c.get('/api/v1/users',headers=h).status_code==403
    assert c.post('/api/v1/auth/change-password',headers=h,json={'current_password':PASSWORD,'new_password':'Changed-password-long-2026!'}).status_code==200
    assert c.get('/api/v1/auth/me',headers=h).status_code==401
    h=login()
    with c.app.state.engine.begin() as conn:
        conn.execute(md.tables['organizations'].update().where(md.tables['organizations'].c.id==a['organization_id']).values(is_active=False))
    assert c.get('/api/v1/auth/me',headers=h).status_code==401
    assert c.post('/api/v1/auth/login',json={'username':'admin_a','password':PASSWORD}).status_code==401

def test_lockout_persists_without_exposing_username(erp):
    c,login,a,b=erp
    for _ in range(5):
        assert c.post('/api/v1/auth/login',json={'username':'admin_a','password':'wrong'}).status_code==401
    assert c.post('/api/v1/auth/login',json={'username':'admin_a','password':PASSWORD}).status_code==401
    with c.app.state.engine.begin() as conn:
        u=md.tables['app_users'];row=conn.execute(sa.select(u).where(u.c.id==a['user_id'])).mappings().one()
        assert row['failed_login_count']==5 and row['locked_until'] is not None
        assert row['password_hash'].startswith('$argon2id$')

def test_unknown_payload_and_site_grant_cross_tenant_rejected(erp):
    import uuid
    c,login,a,b=erp;h=login()
    assert c.post('/api/v1/users',headers=h,json={'employee_id':b['employee_id'],'username':'invalid','password':PASSWORD}).status_code==404
    assert c.post('/api/v1/users',headers=h,json={'employee_id':a['employee_id'],'username':'invalid','password':PASSWORD,'organization_id':b['organization_id']}).status_code==422
    assert c.post('/api/v1/users/'+a['user_id']+'/roles',headers=h,json={'grants':[{'code':'ADMIN','site_id':str(uuid.uuid4())}]}).status_code in (404,409)
