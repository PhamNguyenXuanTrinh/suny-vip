"""Typed CRUD and draft document services; posting is always an explicit workflow."""
from datetime import date,datetime
from decimal import Decimal,ROUND_HALF_UP
from functools import partial
from typing import Annotated
from uuid import UUID
import uuid
import sqlalchemy as sa
from fastapi import APIRouter,Request,HTTPException
from pydantic import ConfigDict,Field,create_model
from backend.app.models import metadata as md,schema
from backend.app.models.base import utcnow
from backend.app.core.security import current
from backend.app.core.tenancy import scope
from backend.app.services.auth import audit

router=APIRouter(prefix='/api/v1',tags=['ERP business data'])
GROUPS={
 'users':('sites','departments','roles'), 'employees':('employees',),
 'customers':('customers','customer_contacts'), 'products':('products',),
 'sales':('sales_orders','sales_order_lines'), 'shipments':('shipments','shipment_lines'),
 'purchasing':('suppliers','purchase_orders','purchase_order_lines'),
 'inventory':('warehouses','warehouse_locations','inventory_lots','inventory_units','inventory_movements','stock_transfers','stock_transfer_lines'),
 'production':('bills_of_materials','bom_lines','work_centers','machines','production_orders','production_order_operations','production_reports'),
 'finance':('supplier_bills','supplier_payments','customer_invoices','customer_invoice_lines','customer_receipts','customer_payment_allocations'),
 'tasks':('tasks','task_assignees','task_updates'),'kpi':('kpi_targets',),
 'audit':('audit_log',),'notifications':('notifications',),
}
PERM={name:group for group,names in GROUPS.items() for name in names}
NAMES={name:('boms' if name=='bills_of_materials' else name.replace('_','-')) for name in PERM}
EDITABLE={'sites','departments','employees','customers','customer_contacts','products','suppliers','warehouses','warehouse_locations','inventory_lots','work_centers','machines','kpi_targets'}
DRAFTS={'sales_orders','purchase_orders','shipments','bills_of_materials','production_orders','tasks','customer_invoices','supplier_bills','customer_receipts','supplier_payments','stock_transfers'}
CHILDREN={'sales_orders':('sales_order_lines','order_id'),'purchase_orders':('purchase_order_lines','purchase_order_id'),'shipments':('shipment_lines','shipment_id'),'bills_of_materials':('bom_lines','bom_id'),'customer_invoices':('customer_invoice_lines','invoice_id'),'stock_transfers':('stock_transfer_lines','transfer_id'),'production_orders':('production_order_operations','production_order_id')}
CALCULATED={
 'sales_orders':{'subtotal_amount','discount_amount','tax_amount','total_amount'},
 'purchase_orders':{'subtotal_amount','tax_amount','total_amount'},
 'sales_order_lines':{'line_total'},'purchase_order_lines':{'received_quantity'},
 'customer_invoices':{'subtotal_amount','tax_amount','total_amount'},'customer_invoice_lines':{'line_total'},
 'supplier_bills':{'total_amount'},
 'production_orders':{'released_quantity','good_quantity','scrap_quantity','actual_start_at','actual_end_at'},
}
SYSTEM={'id','organization_id','created_at','updated_at','created_by','assigned_by','assigned_at','reported_by','actor_user_id','verified_by','verified_at','read_at','uploaded_by','must_change_password','password_hash','remaining_quantity','current_debt_amount','shipped_at','delivered_at','received_at'}
SYSTEM.update({'actual_start_at','actual_end_at'})

def serialize(row):
    if row is None:return None
    return {k:format(v,'f') if isinstance(v,Decimal) else v.isoformat().replace('+00:00','Z') if isinstance(v,(date,datetime)) else v for k,v in dict(row).items()}

def money(value):
    result=int(Decimal(value).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    if not 0<=result<=10**15:raise HTTPException(422,'Giá trị tiền ngoài giới hạn')
    return result

def get(c,table_name,row_id,p,permission):
    t=md.tables[table_name]
    row=c.execute(sa.select(t).where(t.c.id==row_id,scope(table_name,p,permission))).mappings().first()
    if not row:raise HTTPException(404,'Không tìm thấy bản ghi trong phạm vi được phép')
    return dict(row)

def foreign_keys(c,table_name,values,p,permission):
    sites=p.sites(permission)
    for field,info in schema[table_name]['columns'].items():
        v=values.get(field)
        if not v or 'references' not in info or field=='organization_id':continue
        target=info['references'].split('.')[0];t=md.tables[target]
        row=c.execute(sa.select(t).where(t.c.id==v,t.c.organization_id==p.organization_id)).mappings().first()
        if not row:raise HTTPException(404,'Liên kết không tồn tại trong tổ chức')
        if field in ('customer_id','sales_order_id','sales_order_line_id','production_order_id','task_id','warehouse_id','from_warehouse_id','to_warehouse_id','work_center_id','machine_id','inventory_unit_id'):
            get(c,target,v,p,permission)
        if field=='site_id' and sites is not None and v not in sites:raise HTTPException(404,'Cơ sở ngoài phạm vi được phép')
        if field in ('employee_id','owner_employee_id','manager_employee_id') and sites is not None and row.get('site_id') not in sites:raise HTTPException(404,'Nhân viên ngoài phạm vi cơ sở được phép')

def fields(table_name,parent_field=None,patch=False):
    result={}
    for name,s in schema[table_name]['columns'].items():
        if name in SYSTEM or name in CALCULATED.get(table_name,set()) or name==parent_field or s.get('default')=='utcnow':continue
        if name=='status' and table_name not in EDITABLE:continue
        typ=s['type']
        t={'uuid':UUID,'integer':Annotated[int,Field(strict=True,ge=0,le=10**15)],'boolean':Annotated[bool,Field(strict=True)],'quantity':Annotated[Decimal,Field(max_digits=18,decimal_places=6,ge=0)],'datetime':datetime,'date':date,'string':str}[typ]
        opts={}
        if (table_name,name) in {('customer_receipts','amount'),('supplier_payments','amount'),('bills_of_materials','output_quantity'),('production_orders','planned_quantity')} or name=='quantity':opts['gt']=0
        if typ=='string':opts.update(min_length=0 if s['nullable'] else 1,max_length=s['length'] or 10000)
        if 'enum' in s:
            from typing import Literal
            t=Literal[tuple(s['enum'])]
        default=None if patch or s['nullable'] else s.get('default',...)
        if s['nullable'] or patch:t=t|None
        if default=='utcnow':default=...
        result[name]=(t,Field(default=default,**opts))
    return result

MODELS={}
for name in EDITABLE|DRAFTS:
    f=fields(name)
    if name in CHILDREN:
        child,pk=CHILDREN[name]
        line=create_model(name+'LineInput',__config__=ConfigDict(extra='forbid',validate_default=True),**fields(child,pk))
        f['lines']=(list[line],Field(default_factory=list,max_length=200))
    if name=='tasks':f['assignee_ids']=(list[UUID],Field(default_factory=list,max_length=50))
    MODELS[name]=create_model(name+'Create',__config__=ConfigDict(extra='forbid',validate_default=True),**f)

OUTPUTS={}
DETAILS={}
PAGES={}
for name in PERM:
    output_fields={}
    for field,spec in schema[name]['columns'].items():
        typ={'uuid':UUID,'integer':int,'boolean':bool,'quantity':str,'date':date,'datetime':datetime,'string':str}[spec['type']]
        if spec['nullable']:typ=typ|None
        output_fields[field]=(typ,...)
    OUTPUTS[name]=create_model(name+'Output',__config__=ConfigDict(extra='forbid'),**output_fields)
    PAGES[name]=create_model(name+'Page',items=(list[OUTPUTS[name]],...),total=(int,...),page=(int,...),page_size=(int,...))
for name in PERM:
    extra={}
    if name in CHILDREN:extra['lines']=(list[OUTPUTS[CHILDREN[name][0]]],Field(default_factory=list))
    if name=='production_reports':extra['corrections']=(list[dict],Field(default_factory=list))
    if name=='tasks':
        extra['assignees']=(list[dict],Field(default_factory=list))
        extra['assignee_ids']=(list[UUID],Field(default_factory=list))
    if name in ('customer_invoices','supplier_bills','customer_receipts','supplier_payments'):
        extra['allocations']=(list[dict],Field(default_factory=list))
        extra['allocated_amount']=(int,0)
        extra['outstanding_amount' if name in ('customer_invoices','supplier_bills') else 'unallocated_amount']=(int,0)
    DETAILS[name]=create_model(name+'Detail',__base__=OUTPUTS[name],**extra) if extra else OUTPUTS[name]

def normalized(b):
    values={k:str(v) if isinstance(v,UUID) else v for k,v in b.items()}
    aliases={'m²':'m2','m^2':'m2','cuộn':'roll','cuon':'roll','cái':'pcs','cai':'pcs','tấn':'t'}
    for field in ('base_uom','uom'):
        if isinstance(values.get(field),str):
            value=values[field].strip().casefold();values[field]=aliases.get(value,value)
    return values

def totals(c,table_name,rid,p):
    if table_name not in ('sales_orders','purchase_orders','customer_invoices'):return
    child,fk=CHILDREN[table_name];t=md.tables[child];subtotal=tax=discount=0
    rows=c.execute(sa.select(t).where(t.c[fk]==rid,t.c.organization_id==p.organization_id)).mappings().all()
    for row in rows:
        gross=money(row['quantity']*row['unit_price'])
        d=row.get('discount_amount',0)
        if d>gross:raise HTTPException(422,'Chiết khấu vượt giá trị dòng')
        line_tax=money(Decimal(gross-d)*row['tax_rate']/10000) if table_name=='sales_orders' else row['tax_amount']
        if table_name=='sales_orders' and row['tax_rate']>10000:raise HTTPException(422,'Thuế suất vượt giới hạn')
        line_total=gross-d+line_tax
        money(line_total)
        if 'line_total' in t.c:c.execute(t.update().where(t.c.id==row['id']).values(line_total=line_total))
        subtotal+=gross;discount+=d;tax+=line_tax
    changes={'subtotal_amount':subtotal,'tax_amount':tax,'total_amount':subtotal-discount+tax}
    for value in changes.values():money(value)
    if table_name=='sales_orders':changes['discount_amount']=discount
    c.execute(md.tables[table_name].update().where(md.tables[table_name].c.id==rid).values(**changes))

def validate_line(c,parent_name,child_name,row,p,permission):
    foreign_keys(c,child_name,row,p,permission)
    if 'quantity' in row and row['quantity']<=0:raise HTTPException(422,'Số lượng phải lớn hơn 0')
    if 'quantity' in row and 'unit_price' in row:
        gross=money(row['quantity']*row['unit_price'])
        if row.get('discount_amount',0)>gross:raise HTTPException(422,'Chiết khấu vượt giá trị dòng')
    product_field='product_id' if 'product_id' in row else 'component_product_id' if 'component_product_id' in row else None
    if product_field:
        products=md.tables['products'];product=c.execute(sa.select(products).where(products.c.id==row[product_field],products.c.organization_id==p.organization_id)).mappings().one()
        if row.get('uom')!=product['base_uom']:raise HTTPException(422,'Đơn vị tính phải khớp sản phẩm')
        if parent_name in ('sales_orders','purchase_orders'):
            flag='is_sellable' if parent_name=='sales_orders' else 'is_purchasable'
            if not product['is_active'] or not product[flag]:raise HTTPException(409,'Sản phẩm không được phép dùng cho nghiệp vụ này')

def list_data(table_name,request:Request,page:int=1,page_size:int=25,q:str='',sort:str='id',direction:str='asc',status:str|None=None,parent_id:str|None=None,customer_id:str|None=None,warehouse_id:str|None=None,product_id:str|None=None,site_id:str|None=None,owner_employee_id:str|None=None,employee_id:str|None=None,supplier_id:str|None=None,lot_id:str|None=None,is_active:bool|None=None,is_read:bool|None=None,has_stock:bool|None=None):
    if page<1 or not 1<=page_size<=100 or direction not in ('asc','desc') or len(q)>200:raise HTTPException(422,'Bộ lọc không hợp lệ')
    t=md.tables[table_name]
    if sort not in t.c or sort in ('old_json','new_json'):raise HTTPException(422,'Cột sắp xếp không hợp lệ')
    with request.app.state.engine.begin() as c:
        p=current(c,request);permission=PERM[table_name]+'.read'
        if table_name=='notifications':permission='session.read'
        elif table_name=='kpi_targets':permission='kpi.read'
        p.require(permission);clauses=[scope(table_name,p,permission)]
        for field,value in (('customer_id',customer_id),('warehouse_id',warehouse_id),('product_id',product_id),('site_id',site_id),('owner_employee_id',owner_employee_id),('employee_id',employee_id),('supplier_id',supplier_id),('lot_id',lot_id)):
            if value:
                if field not in t.c:raise HTTPException(422,'Bộ lọc không áp dụng cho phân hệ này')
                clauses.append(t.c[field]==value)
        for field,value in (('is_active',is_active),('is_read',is_read)):
            if value is not None:
                if field not in t.c:raise HTTPException(422,'Bộ lọc không áp dụng cho phân hệ này')
                clauses.append(t.c[field].is_(value))
        if has_stock is not None:
            if 'remaining_quantity' not in t.c:raise HTTPException(422,'Bộ lọc tồn chỉ áp dụng cho cuộn tồn kho')
            clauses.append(t.c.remaining_quantity>0 if has_stock else t.c.remaining_quantity==0)
        if status:
            if 'status' not in t.c:raise HTTPException(422,'Bảng không có trạng thái')
            clauses.append(t.c.status==status)
        if q:
            cols=[t.c[n] for n in t.c.keys() if n in ('name','full_name','title','code','sku','invoice_no','bill_no') or n.endswith('_code')]
            clauses.append(sa.or_(*[col.contains(q,autoescape=True) for col in cols]) if cols else sa.false())
        if parent_id:
            from backend.app.core.tenancy import PARENTS
            if table_name not in PARENTS:raise HTTPException(422,'Bảng không có liên kết cha')
            clauses.append(t.c[PARENTS[table_name][0]]==parent_id)
        query=sa.select(t).where(*clauses)
        count=c.execute(sa.select(sa.func.count()).select_from(query.subquery())).scalar_one()
        rows=c.execute(query.order_by(t.c[sort].desc() if direction=='desc' else t.c[sort].asc(),t.c.id).offset((page-1)*page_size).limit(page_size)).mappings().all()
        return {'items':[serialize(r) for r in rows],'total':count,'page':page,'page_size':page_size}

def detail_data(table_name,row_id:str,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);permission=PERM[table_name]+'.read'
        if table_name=='notifications':permission='session.read'
        p.require(permission);result=serialize(get(c,table_name,row_id,p,permission))
        if table_name in CHILDREN:
            child,fk=CHILDREN[table_name];t=md.tables[child]
            result['lines']=[serialize(r) for r in c.execute(sa.select(t).where(t.c[fk]==row_id,t.c.organization_id==p.organization_id)).mappings()]
        if table_name=='production_reports':
            t=md.tables['production_report_corrections']
            result['corrections']=[serialize(r) for r in c.execute(sa.select(t).where(t.c.report_id==row_id,t.c.organization_id==p.organization_id)).mappings()]
        if table_name=='tasks':
            t=md.tables['task_assignees']
            result['assignees']=[serialize(r) for r in c.execute(sa.select(t).where(t.c.task_id==row_id,t.c.organization_id==p.organization_id)).mappings()]
            result['assignee_ids']=[r['employee_id'] for r in result['assignees'] if r['status']!='removed']
        if table_name in ('customer_invoices','supplier_bills','customer_receipts','supplier_payments'):
            from backend.app.services.finance import supplier_allocations,events
            supplier=table_name.startswith('supplier_');invoice=table_name in ('customer_invoices','supplier_bills')
            alloc=supplier_allocations if supplier else md.tables['customer_payment_allocations']
            link=('bill_id' if supplier else 'invoice_id') if invoice else ('payment_id' if supplier else 'receipt_id')
            event_link=events.c.supplier_allocation_id if supplier else events.c.customer_allocation_id
            result['allocations']=[serialize(r) for r in c.execute(sa.select(events.c.id,events.c.amount,events.c.occurred_at,alloc.c['bill_id' if supplier else 'invoice_id'],alloc.c['payment_id' if supplier else 'receipt_id']).join(alloc,alloc.c.id==event_link).where(alloc.c.organization_id==p.organization_id,alloc.c[link]==row_id).order_by(events.c.occurred_at,events.c.id)).mappings()]
            result['allocated_amount']=sum(r['amount'] for r in result['allocations'])
            result['outstanding_amount' if invoice else 'unallocated_amount']=result['total_amount' if invoice else 'amount']-result['allocated_amount']
        return result

def create_data(table_name,body,request:Request):
    permission=PERM[table_name]+'.write'
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require(permission)
        values=normalized(body.model_dump());lines=values.pop('lines',[]);assignees=values.pop('assignee_ids',[])
        if table_name=='customers' and 'CTV' in p.roles and 'ADMIN' not in p.roles:
            if values.get('owner_employee_id') not in (None,p.employee_id):raise HTTPException(403,'Chỉ được quản lý khách hàng của mình')
            values['owner_employee_id']=p.employee_id
        foreign_keys(c,table_name,values,p,permission)
        if table_name in ('sales_orders','purchase_orders'):
            party_table='customers' if table_name=='sales_orders' else 'suppliers';field='customer_id' if table_name=='sales_orders' else 'supplier_id'
            party=c.execute(sa.select(md.tables[party_table].c.status).where(md.tables[party_table].c.id==values[field])).scalar_one()
            if party!='active':raise HTTPException(409,'Khách hàng hoặc nhà cung cấp hiện không nhận đơn mới')
        if table_name=='production_orders':
            products=md.tables['products'];manufactured=c.execute(sa.select(products.c.is_manufactured,products.c.is_active).where(products.c.id==values['product_id'])).one()
            if not all(manufactured):raise HTTPException(409,'Sản phẩm phải đang hoạt động và được đánh dấu tự sản xuất')
        rid=str(uuid.uuid4());values.update(id=rid,organization_id=p.organization_id)
        for field in ('created_by','assigned_by'):
            if field in md.tables[table_name].c:values[field]=p.user_id
        if table_name in ('sales_orders','purchase_orders'):values['ordered_at']=values.get('ordered_at') or utcnow()
        if table_name=='supplier_bills':values['total_amount']=values.get('subtotal_amount',0)+values.get('tax_amount',0)
        if table_name=='stock_transfers':values['requested_at']=utcnow()
        if table_name=='customer_contacts' and values.get('is_primary'):
            t=md.tables[table_name];c.execute(t.update().where(t.c.customer_id==values['customer_id'],t.c.organization_id==p.organization_id).values(is_primary=False))
        c.execute(md.tables[table_name].insert().values(**values))
        if lines:
            child,pk=CHILDREN[table_name]
            for line in lines:
                row=normalized(line);row.update(organization_id=p.organization_id,**{pk:rid})
                validate_line(c,table_name,child,row,p,permission)
                c.execute(md.tables[child].insert().values(**row))
        if table_name in ('sales_orders','purchase_orders','customer_invoices'):
            if not lines:raise HTTPException(422,'Chứng từ cần ít nhất một dòng hàng')
            totals(c,table_name,rid,p)
        if assignees:
            from backend.app.services.tasks import replace_assignees
            replace_assignees(c,p,rid,assignees)
        audit(c,p,'create',table_name,rid)
        return serialize(get(c,table_name,rid,p,permission))

def update_data(table_name,row_id:str,body,request:Request):
    permission=PERM[table_name]+'.write'
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require(permission);old=get(c,table_name,row_id,p,permission)
        if table_name in DRAFTS:
            expected='open' if table_name=='tasks' else 'draft'
            if old.get('status')!=expected:raise HTTPException(409,'Chỉ sửa được chứng từ ở trạng thái nháp')
        values=normalized(body.model_dump(exclude_unset=True))
        lines=values.pop('lines',None)
        assignees=values.pop('assignee_ids',None)
        if not values and lines is None and assignees is None:raise HTTPException(422,'Không có thay đổi')
        if table_name=='customers' and 'CTV' in p.roles and 'ADMIN' not in p.roles and values.get('owner_employee_id',p.employee_id)!=p.employee_id:raise HTTPException(403,'Không được chuyển chủ sở hữu')
        foreign_keys(c,table_name,values,p,permission)
        if table_name=='supplier_bills':values['total_amount']=values.get('subtotal_amount',old['subtotal_amount'])+values.get('tax_amount',old['tax_amount'])
        if table_name=='products' and values.get('base_uom',old['base_uom'])!=old['base_uom']:
            for name,field in [('inventory_units','product_id'),('sales_order_lines','product_id'),('purchase_order_lines','product_id'),('bom_lines','component_product_id'),('bills_of_materials','product_id'),('production_orders','product_id')]:
                t=md.tables[name]
                if c.execute(sa.select(t.c.id).where(t.c[field]==row_id)).first():raise HTTPException(409,'Sản phẩm đã phát sinh nghiệp vụ, không được đổi đơn vị cơ sở')
        if table_name=='customer_contacts' and values.get('is_primary',old['is_primary']):
            t=md.tables[table_name];customer=values.get('customer_id',old['customer_id'])
            c.execute(t.update().where(t.c.customer_id==customer,t.c.organization_id==p.organization_id).values(is_primary=False))
        if assignees is not None:
            from backend.app.services.tasks import replace_assignees
            replace_assignees(c,p,row_id,assignees)
        if 'updated_at' in md.tables[table_name].c:values['updated_at']=utcnow()
        if values:c.execute(md.tables[table_name].update().where(md.tables[table_name].c.id==row_id).values(**values))
        if lines is not None:
            child,pk=CHILDREN[table_name];t=md.tables[child]
            c.execute(t.delete().where(t.c[pk]==row_id,t.c.organization_id==p.organization_id))
            for line in lines:
                row=normalized(line);row.update(organization_id=p.organization_id,**{pk:row_id})
                validate_line(c,table_name,child,row,p,permission)
                c.execute(t.insert().values(**row))
            if table_name in ('sales_orders','purchase_orders','customer_invoices'):
                if not lines:raise HTTPException(422,'Chứng từ cần ít nhất một dòng hàng')
                totals(c,table_name,row_id,p)
        audit(c,p,'update',table_name,row_id)
        return serialize(get(c,table_name,row_id,p,permission))

for table_name,path in NAMES.items():
    router.add_api_route('/'+path,partial(list_data,table_name),methods=['GET'],name='list_'+table_name,response_model=PAGES[table_name])
    router.add_api_route('/'+path+'/{row_id}',partial(detail_data,table_name),methods=['GET'],name='get_'+table_name,response_model=DETAILS[table_name])
    if table_name in MODELS:
        def make_create(name):
            def handler(body,request:Request):return create_data(name,body,request)
            handler.__annotations__['body']=MODELS[name]
            return handler
        router.add_api_route('/'+path,make_create(table_name),methods=['POST'],status_code=201,name='create_'+table_name,response_model=OUTPUTS[table_name])
    if table_name in EDITABLE|DRAFTS:
        edit_fields=fields(table_name,patch=True)
        if table_name in CHILDREN:
            edit_fields['lines']=(list[MODELS[table_name].model_fields['lines'].annotation.__args__[0]]|None,Field(default=None,max_length=200))
        if table_name=='tasks':edit_fields['assignee_ids']=(list[UUID]|None,Field(default=None,max_length=50))
        dto=create_model(table_name+'Edit',__config__=ConfigDict(extra='forbid'),**edit_fields)
        def make_edit(name,dto):
            def handler(row_id:str,body,request:Request):return update_data(name,row_id,body,request)
            handler.__annotations__['body']=dto
            return handler
        router.add_api_route('/'+path+'/{row_id}',make_edit(table_name,dto),methods=['PATCH'],name='update_'+table_name,response_model=OUTPUTS[table_name])

@router.get('/meta/resources')
def resources(request:Request):
    from backend.app.core.security import PERMISSIONS
    with request.app.state.engine.begin() as c:
        p=current(c,request);items=[]
        for name,path in NAMES.items():
            group=PERM[name];read='session.read' if name=='notifications' else group+'.read'
            try:p.require(read)
            except HTTPException:continue
            can_write=any('*' in PERMISSIONS.get(r,set()) or group+'.write' in PERMISSIONS.get(r,set()) for r in p.roles)
            action_permissions={'sales_orders':{'confirm':'sales.confirm'},'purchase_orders':{'approve':'purchasing.write','receive':'purchasing.receive'},'shipments':{'ship':'shipments.ship','deliver':'shipments.deliver'},'stock_transfers':{'ship':'inventory.write','receive':'inventory.write'},'bills_of_materials':{'activate':'production.write'},'production_orders':{'release':'production.write','start':'production.report','reports':'production.report','complete':'production.write'},'customer_invoices':{'issue':'finance.write'},'customer_receipts':{'verify':'finance.write','allocations':'finance.write'},'supplier_bills':{'post':'finance.write'},'supplier_payments':{'verify':'finance.write','allocations':'finance.write'},'tasks':{'updates':'tasks.update'}}
            if name=='tasks':action_permissions[name]['assignees']='tasks.write'
            permitted=[]
            if name=='production_reports':action_permissions[name]={'corrections':'production.write'}
            for action,permission in action_permissions.get(name,{}).items():
                try:p.require(permission);permitted.append(action)
                except HTTPException:pass
            global_actions=[]
            if name in ('inventory_units','inventory_movements'):
                for endpoint,title,permission in [('receipt','Nhập kho','inventory.write'),('issue','Xuất kho','inventory.write'),('adjustment','Điều chỉnh kho','inventory.adjust')]:
                    try:p.require(permission);global_actions.append({'path':'/api/v1/inventory-movements/'+endpoint,'title':title})
                    except HTTPException:pass
            items.append({'table':name,'path':'/api/v1/'+path,'can_create':name in MODELS and can_write,'can_edit':name in EDITABLE|DRAFTS and can_write,'actions':permitted,'global_actions':global_actions,'input_schema':MODELS[name].model_json_schema() if name in MODELS and can_write else None,'columns':[n for n in schema[name]['columns']],'status_values':schema[name]['columns'].get('status',{}).get('enum',[]),'filter_fields':[f for f in ('site_id','owner_employee_id','employee_id','customer_id','supplier_id','warehouse_id','product_id','lot_id','is_active','is_read') if f in schema[name]['columns']]})
        return {'items':items,'organization_id':p.organization_id}

@router.get('/references/{resource}')
def references(resource:str,request:Request,q:str='',record_id:str|None=None,parent_id:str|None=None):
    name=next((n for n,path in NAMES.items() if path==resource),None)
    if name is None:raise HTTPException(404,'Danh mục không tồn tại')
    alternatives={'employees':['employees.read','tasks.write','customers.write','kpi.write'],'sites':['users.read','inventory.write','production.write'],'products':['products.read','inventory.read','production.read'],'customer_invoices':['finance.write'],'supplier_bills':['finance.write'],'purchase_order_lines':['purchasing.receive'],'production_order_operations':['production.report']}
    with request.app.state.engine.begin() as c:
        p=current(c,request);permission=None
        for candidate in alternatives.get(name,[PERM[name]+'.read']):
            try:p.require(candidate);permission=candidate;break
            except HTTPException:pass
        if not permission:raise HTTPException(403,'Không có quyền xem danh mục liên kết')
        t=md.tables[name];clauses=[scope(name,p,permission)]
        if q:
            cols=[t.c[n] for n in t.c.keys() if n in ('name','full_name','title','code','sku','invoice_no','bill_no') or n.endswith('_code')]
            clauses.append(sa.or_(*[col.contains(q[:100],autoescape=True) for col in cols]) if cols else sa.false())
        if record_id:clauses.append(t.c.id==record_id)
        elif 'is_active' in t.c:clauses.append(t.c.is_active.is_(True))
        if name=='employees' and 'CTV' in p.roles and 'ADMIN' not in p.roles:clauses.append(t.c.id==p.employee_id)
        if parent_id:
            from backend.app.core.tenancy import PARENTS
            if name in PARENTS:clauses.append(t.c[PARENTS[name][0]]==parent_id)
        rows=c.execute(sa.select(t).where(*clauses).order_by(t.c.id).limit(100)).mappings().all()
        items=[]
        for row in rows:
            label=' · '.join(str(row[n]) for n in ('code','employee_code','customer_code','supplier_code','bom_code','sku','order_code','po_code','invoice_no','bill_no','roll_code','production_order_code','name','full_name','title','line_no','sequence_no','description') if n in row and row[n] is not None)
            if name=='bills_of_materials':
                products=md.tables['products'];product=c.execute(sa.select(products.c.sku,products.c.name).where(products.c.id==row['product_id'])).one()
                label=f"{row['bom_code']} · Phiên bản {row['version_no']} · {product.sku} · {product.name}"
            if name=='production_order_operations':
                orders=md.tables['production_orders'];centers=md.tables['work_centers']
                code=c.execute(sa.select(orders.c.production_order_code).where(orders.c.id==row['production_order_id'])).scalar_one()
                center=c.execute(sa.select(centers.c.code,centers.c.name).where(centers.c.id==row['work_center_id'])).one()
                label=f"{code} · {row['sequence_no']} · {center.code} · {center.name}"
            if name in ('sales_order_lines','purchase_order_lines'):
                products=md.tables['products'];product=c.execute(sa.select(products.c.sku,products.c.name).where(products.c.id==row['product_id'])).one()
                parent='sales_orders' if name=='sales_order_lines' else 'purchase_orders';parent_field='order_id' if name=='sales_order_lines' else 'purchase_order_id';code_field='order_code' if name=='sales_order_lines' else 'po_code'
                document=c.execute(sa.select(md.tables[parent].c[code_field]).where(md.tables[parent].c.id==row[parent_field])).scalar_one()
                label=f"{document} · {row['line_no']} · {product.sku} · {product.name} · {row['quantity']} {row['uom']}"
            items.append({'id':row['id'],'label':label or 'Bản ghi '+str(row['id'])[:8]})
        return {'items':items,'limit':100}


@router.get('/department-tree')
def department_tree(request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('users.read');t=md.tables['departments']
        rows=c.execute(sa.select(t).where(scope('departments',p,'users.read')).order_by(t.c.name,t.c.id)).mappings().all()
        nodes={r['id']:{**serialize(r),'children':[]} for r in rows};roots=[]
        for node in nodes.values():
            parent=nodes.get(node['parent_department_id'])
            if parent:parent['children'].append(node)
            else:roots.append(node)
        return {'items':roots,'total':len(nodes)}
