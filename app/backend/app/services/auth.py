from datetime import timedelta
import json,uuid
import sqlalchemy as sa
from fastapi import APIRouter,Request,HTTPException
from backend.app.core.security import current,digest,dummy_hash,hash_password,issue,verify,sessions
from backend.app.models import metadata as md
from backend.app.models.base import utcnow
from backend.app.schemas.auth import Login,Refresh,PasswordChange,UserCreate,UserEdit,Grants

router=APIRouter(prefix='/api/v1',tags=['Authentication and authorization'])

def audit(c,p,action,entity,entity_id=None,data=None):
    scheduled=p.session_id=='system-job'
    payload={**(data or {}),**({'initiator':'scheduled_rule_job'} if scheduled else {})}
    c.execute(md.tables['audit_log'].insert().values(organization_id=p.organization_id,actor_user_id=None if scheduled else p.user_id,action=action,entity_type=entity,entity_id=entity_id,request_id=p.request_id,new_json=json.dumps(payload,ensure_ascii=False)))

@router.post('/auth/login')
def login(b:Login,request:Request):
    t=md.tables['app_users'];org=md.tables['organizations'];emp=md.tables['employees'];error=False
    with request.app.state.engine.begin() as c:
        row=c.execute(sa.select(t,org.c.is_active.label('org_active'),emp.c.status.label('employee_status')).join(org,t.c.organization_id==org.c.id).join(emp,t.c.employee_id==emp.c.id).where(t.c.username==b.username.strip().lower())).mappings().first()
        locked=row and row['locked_until'] and row['locked_until']>utcnow()
        valid=verify(b.password,row['password_hash'] if row else dummy_hash())
        if locked or not row or not valid or not row['is_active'] or not row['org_active'] or row['employee_status']!='active':
            error=True
            if row and not locked:
                failures=row['failed_login_count']+1
                c.execute(t.update().where(t.c.id==row['id']).values(failed_login_count=failures,locked_until=utcnow()+timedelta(minutes=15) if failures>=5 else None))
                c.execute(md.tables['audit_log'].insert().values(organization_id=row['organization_id'],actor_user_id=None,action='login_failed',entity_type='app_users',entity_id=row['id'],request_id=request.state.request_id))
        else:
            c.execute(t.update().where(t.c.id==row['id']).values(failed_login_count=0,locked_until=None,last_login_at=utcnow()))
            result=issue(c,row,request.app.state.settings)
            c.execute(md.tables['audit_log'].insert().values(organization_id=row['organization_id'],actor_user_id=row['id'],action='login',entity_type='app_users',entity_id=row['id'],request_id=request.state.request_id))
    if error:raise HTTPException(401,'Sai tài khoản hoặc mật khẩu hoặc tài khoản tạm khóa')
    return result

@router.post('/auth/refresh')
def refresh(b:Refresh,request:Request):
    error=False
    with request.app.state.engine.begin() as c:
        row=c.execute(sa.select(sessions).where(sessions.c.refresh_hash==digest(b.refresh_token))).mappings().first()
        if not row or row['expires_at']<=utcnow():error=True
        elif row['revoked_at']:
            c.execute(sessions.update().where(sessions.c.family_id==row['family_id']).values(revoked_at=utcnow()));error=True
        else:
            u=md.tables['app_users'];o=md.tables['organizations'];e=md.tables['employees']
            user=c.execute(sa.select(u).join(o,u.c.organization_id==o.c.id).join(e,u.c.employee_id==e.c.id).where(u.c.id==row['user_id'],u.c.is_active.is_(True),o.c.is_active.is_(True),e.c.status=='active')).mappings().first()
            if not user:error=True
            else:
                c.execute(sessions.update().where(sessions.c.id==row['id']).values(revoked_at=utcnow()))
                result=issue(c,user,request.app.state.settings,row['family_id'])
    if error:raise HTTPException(401,'Phiên đăng nhập không hợp lệ')
    return result

@router.get('/auth/me')
def me(request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request,True)
        emp=c.execute(sa.select(md.tables['employees']).where(md.tables['employees'].c.id==p.employee_id)).mappings().one()
        return {'id':p.user_id,'organization_id':p.organization_id,'employee_id':p.employee_id,'username':p.username,'full_name':emp['full_name'],'roles':sorted(p.roles),'grants':p.grants,'must_change_password':p.must_change_password}

@router.post('/auth/logout')
def logout(request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request,True)
        c.execute(sessions.update().where(sessions.c.id==p.session_id).values(revoked_at=utcnow()))
    return {'revoked':True}

@router.post('/auth/change-password')
def change_password(b:PasswordChange,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request,True);t=md.tables['app_users']
        user=c.execute(sa.select(t).where(t.c.id==p.user_id)).mappings().one()
        if not verify(b.current_password,user['password_hash']):raise HTTPException(401,'Mật khẩu hiện tại không đúng')
        c.execute(t.update().where(t.c.id==p.user_id).values(password_hash=hash_password(b.new_password),must_change_password=False,updated_at=utcnow()))
        c.execute(sessions.update().where(sessions.c.user_id==p.user_id).values(revoked_at=utcnow()))
        audit(c,p,'password_change','app_users',p.user_id)
    return {'changed':True,'requires_login':True}

@router.get('/users')
def users(request:Request,page:int=1,page_size:int=25,q:str='',sort:str='username',direction:str='asc'):
    if page<1 or not 1<=page_size<=100 or len(q)>200 or sort not in ('id','username','is_active','employee_id','must_change_password','created_at') or direction not in ('asc','desc'):raise HTTPException(422,'Phân trang hoặc bộ lọc không hợp lệ')
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('users.read');t=md.tables['app_users'];search=q
        q=sa.select(t.c.id,t.c.employee_id,t.c.username,t.c.is_active,t.c.must_change_password).where(t.c.organization_id==p.organization_id)
        if search:q=q.where(t.c.username.contains(search,autoescape=True))
        rows=c.execute(q.order_by(t.c[sort].desc() if direction=='desc' else t.c[sort].asc(),t.c.id).offset((page-1)*page_size).limit(page_size)).mappings().all()
        return {'items':[dict(x) for x in rows],'total':c.execute(sa.select(sa.func.count()).select_from(q.subquery())).scalar_one(),'page':page,'page_size':page_size}

@router.post('/users',status_code=201)
def create_user(b:UserCreate,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('users.write');t=md.tables['employees']
        if not c.execute(sa.select(t.c.id).where(t.c.id==str(b.employee_id),t.c.organization_id==p.organization_id)).first():raise HTTPException(404,'Không tìm thấy nhân viên')
        rid=str(uuid.uuid4())
        c.execute(md.tables['app_users'].insert().values(id=rid,organization_id=p.organization_id,employee_id=str(b.employee_id),username=b.username,password_hash=hash_password(b.password),must_change_password=True))
        audit(c,p,'create','app_users',rid)
    return {'id':rid,'must_change_password':True}

@router.get('/users/{user_id}')
def user_detail(user_id:str,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('users.read');t=md.tables['app_users']
        row=c.execute(sa.select(t.c.id,t.c.employee_id,t.c.username,t.c.is_active,t.c.must_change_password,t.c.created_at).where(t.c.id==user_id,t.c.organization_id==p.organization_id)).mappings().first()
        if not row:raise HTTPException(404,'Không tìm thấy tài khoản')
        return dict(row)

@router.patch('/users/{user_id}')
def edit_user(user_id:str,b:UserEdit,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('users.write');t=md.tables['app_users']
        user=c.execute(sa.select(t).where(t.c.id==user_id,t.c.organization_id==p.organization_id)).mappings().first()
        if not user:raise HTTPException(404,'Không tìm thấy tài khoản')
        if p.user_id==user_id and b.is_active is False:raise HTTPException(409,'Không được tự khóa tài khoản quản trị')
        changes={}
        if b.is_active is not None:changes['is_active']=b.is_active
        if b.new_password:changes.update(password_hash=hash_password(b.new_password),must_change_password=True)
        if changes:
            c.execute(t.update().where(t.c.id==user_id).values(**changes,updated_at=utcnow()))
            c.execute(sessions.update().where(sessions.c.user_id==user_id).values(revoked_at=utcnow()))
            audit(c,p,'update','app_users',user_id,{'is_active':b.is_active,'password_reset':bool(b.new_password)})
    return {'id':user_id,'updated':True}

@router.post('/users/{user_id}/roles')
def grant_roles(user_id:str,b:Grants,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('users.write');u=md.tables['app_users'];r=md.tables['roles'];ur=md.tables['user_roles']
        if not c.execute(sa.select(u.c.id).where(u.c.id==user_id,u.c.organization_id==p.organization_id)).first():raise HTTPException(404,'Không tìm thấy tài khoản')
        if p.user_id==user_id and not any(g.code=='ADMIN' and g.site_id is None for g in b.grants):raise HTTPException(409,'Không được tự thu hồi quyền quản trị')
        seen=set();rows=[]
        for grant in b.grants:
            key=(grant.code,str(grant.site_id) if grant.site_id else None)
            if key in seen:raise HTTPException(422,'Vai trò bị trùng')
            seen.add(key)
            if grant.site_id:
                sites=md.tables['sites']
                if not c.execute(sa.select(sites.c.id).where(sites.c.id==str(grant.site_id),sites.c.organization_id==p.organization_id)).first():raise HTTPException(404,'Không tìm thấy cơ sở')
            role_id=c.execute(sa.select(r.c.id).where(r.c.organization_id==p.organization_id,r.c.code==grant.code,r.c.is_active.is_(True))).scalar_one_or_none()
            if not role_id:raise HTTPException(422,'Vai trò chưa được cấu hình')
            rows.append({'organization_id':p.organization_id,'user_id':user_id,'role_id':role_id,'site_id':key[1],'assigned_by':p.user_id})
        c.execute(ur.delete().where(ur.c.organization_id==p.organization_id,ur.c.user_id==user_id))
        if rows:c.execute(ur.insert(),rows)
        audit(c,p,'roles_changed','app_users',user_id,{'roles':[x.code for x in b.grants]})
    return {'id':user_id,'roles_updated':True}


@router.get('/auth/sessions')
def active_sessions(request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request)
        rows=c.execute(sa.select(sessions.c.id,sessions.c.created_at,sessions.c.expires_at).where(sessions.c.organization_id==p.organization_id,sessions.c.user_id==p.user_id,sessions.c.revoked_at.is_(None),sessions.c.expires_at>utcnow()).order_by(sessions.c.created_at.desc())).mappings().all()
        return {'items':[{**dict(r),'current':r['id']==p.session_id} for r in rows],'limit':request.app.state.settings.max_sessions}

@router.post('/auth/sessions/{session_id}/revoke')
def revoke_session(session_id:str,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);row=c.execute(sa.select(sessions).where(sessions.c.id==session_id,sessions.c.organization_id==p.organization_id,sessions.c.user_id==p.user_id)).mappings().first()
        if not row:raise HTTPException(404,'Không tìm thấy phiên của tài khoản này')
        c.execute(sessions.update().where(sessions.c.organization_id==p.organization_id,sessions.c.user_id==p.user_id,sessions.c.family_id==row['family_id'],sessions.c.revoked_at.is_(None)).values(revoked_at=utcnow()))
        audit(c,p,'revoke_session','auth_sessions',session_id)
        return {'revoked':True,'current':row['family_id']==c.execute(sa.select(sessions.c.family_id).where(sessions.c.id==p.session_id)).scalar_one()}
