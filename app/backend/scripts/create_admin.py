import argparse,getpass,uuid
import sqlalchemy as sa
from backend.app.core.security import hash_password,PERMISSIONS
from backend.app.database import make_engine
from backend.app.models import metadata as md
from backend.scripts.migrate_db import migrate

def provision(engine,code,name,username,password,must_change=True):
    with engine.begin() as c:
        orgs=md.tables['organizations'];users=md.tables['app_users']
        if c.execute(sa.select(orgs.c.id).where(orgs.c.code==code)).first():raise ValueError('Organization already exists; no data changed')
        oid,eid,uid=[str(uuid.uuid4()) for _ in range(3)]
        c.execute(orgs.insert().values(id=oid,code=code,name=name))
        c.execute(md.tables['employees'].insert().values(id=eid,organization_id=oid,employee_code='ADMIN',full_name='Quản trị hệ thống'))
        c.execute(users.insert().values(id=uid,organization_id=oid,employee_id=eid,username=username.strip().lower(),password_hash=hash_password(password),must_change_password=must_change))
        for role in PERMISSIONS:
            rid=str(uuid.uuid4());c.execute(md.tables['roles'].insert().values(id=rid,organization_id=oid,code=role,name=role,is_system=True))
            if role=='ADMIN':c.execute(md.tables['user_roles'].insert().values(organization_id=oid,user_id=uid,role_id=rid,assigned_by=uid))
    return {'organization_id':oid,'employee_id':eid,'user_id':uid,'username':username.strip().lower()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--organization-code',default='SUNNY');p.add_argument('--organization-name',default='SUNNY GROUP');p.add_argument('--username',default='admin');a=p.parse_args()
    password=getpass.getpass('Mật khẩu quản trị (tối thiểu 12 ký tự): ')
    if password!=getpass.getpass('Nhập lại mật khẩu: '):raise SystemExit('Mật khẩu không trùng nhau')
    migrate(a.database)
    engine=make_engine('sqlite:///'+a.database)
    print(provision(engine,a.organization_code,a.organization_name,a.username,password))
