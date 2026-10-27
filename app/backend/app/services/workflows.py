import hashlib,json,uuid
from contextlib import contextmanager
from pydantic import BaseModel,ConfigDict
import sqlalchemy as sa
from fastapi import APIRouter,Request,HTTPException
from backend.app.models import metadata as md
from backend.app.models.base import UTCDateTime,utcnow
from backend.app.core.security import current
from backend.app.services.auth import audit
from backend.app.services.data import get,serialize

from backend.app.schemas.common import PostingRouter
router=PostingRouter(prefix='/api/v1',tags=['Transactional workflows'])
keys=sa.Table('operation_keys',md,
    sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),nullable=False),sa.Column('actor_user_id',sa.String(36),nullable=False),sa.Column('key',sa.String(120),nullable=False),sa.Column('route',sa.String(250),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),sa.Column('result_json',sa.Text(),nullable=False),sa.Column('created_at',UTCDateTime(),nullable=False),sa.UniqueConstraint('organization_id','key'),sa.ForeignKeyConstraint(['organization_id','actor_user_id'],['app_users.organization_id','app_users.id']))

class Empty(BaseModel):model_config=ConfigDict(extra='forbid')

def perform(request,permission,body,callback):
    key=request.headers.get('Idempotency-Key','')
    if not 8<=len(key)<=120:raise HTTPException(422,'Cần Idempotency-Key từ 8 đến 120 ký tự')
    route=request.url.path
    data=body.model_dump(mode='json') if hasattr(body,'model_dump') else body
    digest=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require(permission)
        old=c.execute(sa.select(keys).where(keys.c.organization_id==p.organization_id,keys.c.key==key)).mappings().first()
        if old:
            if old['route']!=route or old['payload_hash']!=digest or old['actor_user_id']!=p.user_id:raise HTTPException(409,'Khóa chống lặp đã dùng với nội dung hoặc thao tác khác')
            return json.loads(old['result_json'])
        result=callback(c,p,key)
        c.execute(keys.insert().values(id=str(uuid.uuid4()),organization_id=p.organization_id,actor_user_id=p.user_id,key=key,route=route,payload_hash=digest,result_json=json.dumps(result,ensure_ascii=False),created_at=utcnow()))
        return result

def transition(c,p,name,rid,permission,allowed,target):
    row=get(c,name,rid,p,permission)
    if row['status'] not in allowed:raise HTTPException(409,'Trạng thái hiện tại không cho phép thao tác')
    if name in ('sales_orders','purchase_orders'):
        from backend.app.services.data import CHILDREN
        child,fk=CHILDREN[name];t=md.tables[child]
        if not c.execute(sa.select(t.c.id).where(t.c[fk]==rid)).first():raise HTTPException(409,'Chứng từ chưa có dòng hàng')
    if name in ('sales_orders','purchase_orders') and target in ('confirmed','approved'):
        from backend.app.services.data import validate_line
        child,fk=('sales_order_lines','order_id') if name=='sales_orders' else ('purchase_order_lines','purchase_order_id')
        party_table='customers' if name=='sales_orders' else 'suppliers';party_field='customer_id' if name=='sales_orders' else 'supplier_id'
        party=md.tables[party_table]
        if c.execute(sa.select(party.c.status).where(party.c.id==row[party_field],party.c.organization_id==p.organization_id)).scalar_one()!='active':raise HTTPException(409,'Khách hàng hoặc nhà cung cấp đã ngừng hoạt động')
        line_table=md.tables[child]
        for line in c.execute(sa.select(line_table).where(line_table.c[fk]==rid,line_table.c.organization_id==p.organization_id)).mappings():validate_line(c,name,child,dict(line),p,permission)
    changes={'status':target}
    if 'updated_at' in md.tables[name].c:changes['updated_at']=utcnow()
    c.execute(md.tables[name].update().where(md.tables[name].c.id==rid).values(**changes))
    audit(c,p,target,name,rid)
    return {'id':rid,'status':target}

@router.post('/sales-orders/{row_id}/confirm')
def confirm(row_id:str,body:Empty,request:Request):
    return perform(request,'sales.confirm',body,lambda c,p,key:transition(c,p,'sales_orders',row_id,'sales.confirm',{'draft'},'confirmed'))

@router.post('/purchase-orders/{row_id}/approve')
def approve(row_id:str,body:Empty,request:Request):
    return perform(request,'purchasing.write',body,lambda c,p,key:transition(c,p,'purchase_orders',row_id,'purchasing.write',{'draft'},'approved'))
