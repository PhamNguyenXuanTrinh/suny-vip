import uuid
import sqlalchemy as sa
from backend.app.models import metadata as md
from backend.app.core.security import current
from backend.app.core.tenancy import scope
from .conftest import add_user

def test_ctv_uses_employee_id_and_sites_are_enforced(erp):
    c,login,a,b=erp;oid=a['organization_id']
    uid,eid=add_user(c,oid,'ctv_a');uid2,eid2=add_user(c,oid,'ctv_b')
    with c.app.state.engine.begin() as conn:
        for code,emp in [('CA',eid),('CB',eid2)]:conn.execute(md.tables['customers'].insert().values(organization_id=oid,customer_code=code,name=code,owner_employee_id=emp))
    tokens=login('ctv_a')
    from backend.app.core.security import principal
    with c.app.state.engine.begin() as conn:
        p=principal(conn,tokens['Authorization'][7:],c.app.state.settings)
        assert p.employee_id!=p.user_id
        customers=md.tables['customers']
        assert conn.execute(sa.select(customers.c.customer_code).where(scope('customers',p,'customers.read'))).scalars().all()==['CA']
        s1,s2=str(uuid.uuid4()),str(uuid.uuid4())
        conn.execute(md.tables['sites'].insert(),[{'id':s1,'organization_id':oid,'code':'S1','name':'One'},{'id':s2,'organization_id':oid,'code':'S2','name':'Two'}])
        for sid in (s1,s2):conn.execute(md.tables['warehouses'].insert().values(organization_id=oid,site_id=sid,code=sid,name='Warehouse'))
    uid3,eid3=add_user(c,oid,'qc','QC_LEADER',site_id=s1)
    h=login('qc')
    with c.app.state.engine.begin() as conn:
        p=principal(conn,h['Authorization'][7:],c.app.state.settings)
        wh=md.tables['warehouses']
        assert conn.execute(sa.select(wh.c.site_id).where(scope('warehouses',p,'inventory.read'))).scalars().all()==[s1]
