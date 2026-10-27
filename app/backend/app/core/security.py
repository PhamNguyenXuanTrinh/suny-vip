"""Argon2id, short JWTs and revocable refresh families. Roles are read on every request."""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from functools import lru_cache
import hashlib,secrets,uuid
import jwt
import sqlalchemy as sa
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from fastapi import HTTPException,Request
from backend.app.models import metadata
from backend.app.models.base import UTCDateTime,utcnow

ph=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1)
@lru_cache(maxsize=1)
def dummy_hash():return ph.hash(secrets.token_urlsafe(24))

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def hash_password(value):
    if not isinstance(value,str) or not 12<=len(value)<=128:raise HTTPException(422,'Mật khẩu cần từ 12 đến 128 ký tự')
    return ph.hash(value)

def verify(value,hashed):
    try:return ph.verify(hashed,value)
    except (VerificationError,InvalidHashError):return False

sessions=sa.Table('auth_sessions',metadata,
    sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),nullable=False),
    sa.Column('user_id',sa.String(36),nullable=False),sa.Column('family_id',sa.String(36),nullable=False,index=True),
    sa.Column('refresh_hash',sa.String(64),nullable=False,unique=True),sa.Column('created_at',UTCDateTime(),nullable=False),
    sa.Column('expires_at',UTCDateTime(),nullable=False),sa.Column('revoked_at',UTCDateTime()),
    sa.ForeignKeyConstraint(['organization_id','user_id'],['app_users.organization_id','app_users.id']))

def issue(c,user,settings,family_id=None):
    sid=str(uuid.uuid4());refresh=secrets.token_urlsafe(48);now=utcnow()
    c.execute(sessions.insert().values(id=sid,organization_id=user['organization_id'],user_id=user['id'],family_id=family_id or str(uuid.uuid4()),refresh_hash=digest(refresh),created_at=now,expires_at=now+timedelta(seconds=settings.refresh_seconds)))
    active=c.execute(sa.select(sessions.c.family_id,sa.func.max(sessions.c.created_at).label('latest')).where(sessions.c.organization_id==user['organization_id'],sessions.c.user_id==user['id'],sessions.c.revoked_at.is_(None),sessions.c.expires_at>now).group_by(sessions.c.family_id).order_by(sa.func.max(sessions.c.created_at).desc())).all()
    for family,_ in active[settings.max_sessions:]:c.execute(sessions.update().where(sessions.c.organization_id==user['organization_id'],sessions.c.user_id==user['id'],sessions.c.family_id==family,sessions.c.revoked_at.is_(None)).values(revoked_at=now))
    access=jwt.encode({'sub':user['id'],'sid':sid,'iat':int(now.timestamp()),'exp':int(now.timestamp())+settings.access_seconds,'iss':'sunny-erp','aud':'sunny-erp'},settings.jwt_secret,algorithm='HS256')
    return {'access_token':access,'refresh_token':refresh,'token_type':'bearer','expires_in':settings.access_seconds,'must_change_password':bool(user['must_change_password'])}

PERMISSIONS={
 'ADMIN':{'*'},
 'SALES':{'customers.read','customers.write','products.read','sales.read','sales.write','sales.confirm','shipments.read','shipments.write','shipments.deliver','finance.read','tasks.read','tasks.write','kpi.read'},
 'CTV':{'customers.read','customers.write','products.read','sales.read','sales.write','tasks.read','kpi.read'},
 'ACCOUNTANT':{'employees.read','customers.read','products.read','sales.read','purchasing.read','purchasing.write','inventory.read','finance.read','finance.write','reports.read','tasks.read','kpi.read'},
 'QC_LEADER':{'products.read','inventory.read','inventory.write','production.read','production.write','purchasing.read','purchasing.receive','shipments.read','shipments.write','shipments.ship','shipments.deliver','tasks.read','tasks.write','kpi.read'},
 'WORKER':{'inventory.read','production.read','production.report','tasks.read','tasks.update','kpi.read'},
}
PERMISSIONS['QC_LEADER'].add('production.report')
for permissions in PERMISSIONS.values():
    permissions.add('documents.write')
    if 'tasks.read' in permissions:permissions.add('tasks.update')

@dataclass
class Principal:
    user_id:str
    organization_id:str
    employee_id:str
    username:str
    grants:list
    session_id:str
    must_change_password:bool
    request_id:str|None=None

    @property
    def roles(self):return {g['code'] for g in self.grants}

    @property
    def is_global_admin(self):return any(g['code']=='ADMIN' and g['site_id'] is None for g in self.grants)

    def matching_grants(self,permission):
        if permission in ('users.read','users.write','audit.read','jobs.run') and not self.is_global_admin:
            raise HTTPException(403,'Thao tác yêu cầu quản trị toàn tổ chức')
        grants=[g for g in self.grants if permission in PERMISSIONS.get(g['code'],set()) or '*' in PERMISSIONS.get(g['code'],set())]
        if not grants:raise HTTPException(403,'Không có quyền thực hiện thao tác này')
        return grants

    def sites(self,permission):
        if permission=='session.read':return None
        grants=self.matching_grants(permission)
        if any(g['site_id'] is None for g in grants):return None
        return {g['site_id'] for g in grants}

    def require(self,permission):
        if self.must_change_password:raise HTTPException(403,'Cần đổi mật khẩu trước khi sử dụng')
        sites=self.sites(permission)
        if permission.startswith('users.') and sites is not None:raise HTTPException(403,'Quản trị tài khoản yêu cầu quyền toàn tổ chức')

def principal(c,token,settings,allow_password_change=False):
    try:
        claims=jwt.decode(token,settings.jwt_secret,algorithms=['HS256'],issuer='sunny-erp',audience='sunny-erp',options={'require':['sub','sid','exp','iat']})
    except jwt.PyJWTError:raise HTTPException(401,'Phiên đăng nhập không hợp lệ')
    users=metadata.tables['app_users'];orgs=metadata.tables['organizations'];employees=metadata.tables['employees']
    user=c.execute(sa.select(users).join(orgs,users.c.organization_id==orgs.c.id).join(employees,users.c.employee_id==employees.c.id).join(sessions,sa.and_(sessions.c.user_id==users.c.id,sessions.c.id==claims['sid'])).where(users.c.id==claims['sub'],users.c.is_active.is_(True),orgs.c.is_active.is_(True),employees.c.status=='active',sessions.c.revoked_at.is_(None),sessions.c.expires_at>utcnow())).mappings().first()
    if not user:raise HTTPException(401,'Phiên đăng nhập không hợp lệ')
    r=metadata.tables['roles'];ur=metadata.tables['user_roles']
    grants=[dict(g) for g in c.execute(sa.select(r.c.code,ur.c.site_id).join(ur,ur.c.role_id==r.c.id).where(ur.c.user_id==user['id'],r.c.organization_id==user['organization_id'],r.c.is_active.is_(True))).mappings()]
    return Principal(user['id'],user['organization_id'],user['employee_id'],user['username'],grants,claims['sid'],bool(user['must_change_password']))

def current(c,request,allow_password_change=False):
    h=request.headers.get('Authorization','')
    if not h.startswith('Bearer ') or h.count(' ')!=1 or len(h)>4096:raise HTTPException(401,'Cần đăng nhập')
    p=principal(c,h[7:],request.app.state.settings)
    p.request_id=getattr(request.state,'request_id',None)
    if p.must_change_password and not allow_password_change:raise HTTPException(403,'Cần đổi mật khẩu trước khi sử dụng')
    return p
