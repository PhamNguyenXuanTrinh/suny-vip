from uuid import UUID
import uuid
import sqlalchemy as sa
from fastapi import APIRouter,Request,HTTPException
from pydantic import Field
from backend.app.models import metadata as md
from backend.app.models.base import UTCDateTime,utcnow
from backend.app.services.data import get,totals
from backend.app.services.inventory import Input
from backend.app.services.auth import audit
from backend.app.services.workflows import Empty,perform,transition

from backend.app.schemas.common import PostingRouter
router=PostingRouter(prefix='/api/v1',tags=['Receivables and payables'])
supplier_allocations=sa.Table('supplier_payment_allocations',md,
    sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),nullable=False),sa.Column('payment_id',sa.String(36),nullable=False),sa.Column('bill_id',sa.String(36),nullable=False),sa.Column('amount',sa.BigInteger,nullable=False),sa.Column('created_at',UTCDateTime(),nullable=False),sa.Column('created_by',sa.String(36),nullable=False),sa.UniqueConstraint('payment_id','bill_id'),sa.UniqueConstraint('organization_id','id'))
events=sa.Table('payment_allocation_events',md,
    sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),nullable=False),sa.Column('customer_allocation_id',sa.String(36)),sa.Column('supplier_allocation_id',sa.String(36)),sa.Column('amount',sa.BigInteger,nullable=False),sa.Column('occurred_at',UTCDateTime(),nullable=False),sa.Column('actor_user_id',sa.String(36),nullable=False))
for field,target in [('payment_id','supplier_payments'),('bill_id','supplier_bills'),('created_by','app_users')]:
    supplier_allocations.append_constraint(sa.ForeignKeyConstraint(['organization_id',field],[target+'.organization_id',target+'.id']))
for field,target in [('customer_allocation_id','customer_payment_allocations'),('supplier_allocation_id','supplier_payment_allocations'),('actor_user_id','app_users')]:
    events.append_constraint(sa.ForeignKeyConstraint(['organization_id',field],[target+'.organization_id',target+'.id']))
sa.Index('ix_payment_events_tenant_time',events.c.organization_id,events.c.occurred_at)

class Allocation(Input):
    invoice_id:UUID
    amount:int=Field(strict=True,gt=0,le=10**15)
class SupplierAllocation(Input):
    bill_id:UUID
    amount:int=Field(strict=True,gt=0,le=10**15)

def allocated(c,table,field,rid):
    return c.execute(sa.select(sa.func.coalesce(sa.func.sum(table.c.amount),0)).where(table.c[field]==rid)).scalar_one()

def rebuild_debt(c,org,customer_id,apply=True):
    invoices=md.tables['customer_invoices'];a=md.tables['customer_payment_allocations']
    rows=c.execute(sa.select(invoices).where(invoices.c.organization_id==org,invoices.c.customer_id==customer_id,invoices.c.status.in_(['issued','partially_paid','paid','overdue']))).mappings().all()
    amount=sum(r['total_amount']-allocated(c,a,'invoice_id',r['id']) for r in rows)
    if apply:c.execute(md.tables['customers'].update().where(md.tables['customers'].c.id==customer_id).values(current_debt_amount=amount,updated_at=utcnow()))
    return amount

@router.post('/customer-invoices/{row_id}/issue')
def issue_invoice(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        invoice=get(c,'customer_invoices',row_id,p,'finance.write')
        if invoice['status']!='draft':raise HTTPException(409,'Chỉ phát hành được hóa đơn nháp')
        lines=md.tables['customer_invoice_lines'];rows=c.execute(sa.select(lines).where(lines.c.invoice_id==row_id)).mappings().all()
        if not rows:raise HTTPException(409,'Hóa đơn chưa có dòng hàng')
        if invoice['sales_order_id']:
            order=get(c,'sales_orders',invoice['sales_order_id'],p,'finance.write')
            if order['status'] not in ('confirmed','in_progress','completed'):raise HTTPException(409,'Đơn bán chưa được xác nhận')
            for line in rows:
                if not line['sales_order_line_id']:raise HTTPException(422,'Cần chỉ định dòng đơn bán nguồn')
                src=get(c,'sales_order_lines',line['sales_order_line_id'],p,'finance.write')
                if src['order_id']!=order['id']:raise HTTPException(422,'Dòng hóa đơn không khớp đơn bán')
        pending={}
        for line in rows:
            if line['sales_order_line_id']:
                src=get(c,'sales_order_lines',line['sales_order_line_id'],p,'finance.write')
                source_order=get(c,'sales_orders',src['order_id'],p,'finance.write')
                if source_order['customer_id']!=invoice['customer_id']:raise HTTPException(422,'Dòng hóa đơn không thuộc khách hàng này')
                if source_order['status'] not in ('confirmed','in_progress','completed'):raise HTTPException(409,'Đơn bán chưa được xác nhận')
                if line['uom']!=src['uom']:raise HTTPException(422,'Đơn vị hóa đơn phải khớp dòng đơn bán')
                source_id=src['id'];pending[source_id]=pending.get(source_id,0)+line['quantity']
                invoices=md.tables['customer_invoices']
                used=c.execute(sa.select(lines.c.quantity).join(invoices,invoices.c.id==lines.c.invoice_id).where(lines.c.organization_id==p.organization_id,lines.c.sales_order_line_id==source_id,invoices.c.status.in_(['issued','partially_paid','paid','overdue']))).scalars().all()
                if sum(used)+pending[source_id]>src['quantity']:raise HTTPException(409,'Tổng số lượng hóa đơn vượt số lượng đơn bán')
        totals(c,'customer_invoices',row_id,p)
        result=transition(c,p,'customer_invoices',row_id,'finance.write',{'draft'},'issued')
        result['customer_debt_amount']=rebuild_debt(c,p.organization_id,invoice['customer_id'])
        return result
    return perform(request,'finance.write',b,run)

@router.post('/customer-receipts/{row_id}/verify')
def verify_receipt(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        row=get(c,'customer_receipts',row_id,p,'finance.write')
        if row['amount']<=0:raise HTTPException(422,'Số tiền phải lớn hơn 0')
        result=transition(c,p,'customer_receipts',row_id,'finance.write',{'draft'},'verified')
        c.execute(md.tables['customer_receipts'].update().where(md.tables['customer_receipts'].c.id==row_id).values(verified_by=p.user_id,received_at=utcnow()))
        return result
    return perform(request,'finance.write',b,run)

def allocate(c,p,payment_id,invoice_id,amount,supplier=False):
    payment_table='supplier_payments' if supplier else 'customer_receipts'
    invoice_table='supplier_bills' if supplier else 'customer_invoices'
    pay_field='payment_id' if supplier else 'receipt_id';inv_field='bill_id' if supplier else 'invoice_id'
    party='supplier_id' if supplier else 'customer_id'
    payment=get(c,payment_table,payment_id,p,'finance.write');invoice=get(c,invoice_table,invoice_id,p,'finance.write')
    if payment[party]!=invoice[party]:raise HTTPException(422,'Khoản tiền và hóa đơn phải thuộc cùng đối tượng')
    if payment['status']!='verified':raise HTTPException(409,'Khoản tiền chưa được xác nhận')
    if invoice['status'] not in (('posted','partially_paid') if supplier else ('issued','partially_paid','overdue')):raise HTTPException(409,'Hóa đơn không còn ở trạng thái được phân bổ')
    table=supplier_allocations if supplier else md.tables['customer_payment_allocations']
    paid=allocated(c,table,pay_field,payment_id);used=allocated(c,table,inv_field,invoice_id)
    if amount>payment['amount']-paid or amount>invoice['total_amount']-used:raise HTTPException(409,'Số tiền phân bổ vượt số dư phiếu thu/chi hoặc hóa đơn')
    old=c.execute(sa.select(table).where(table.c[pay_field]==payment_id,table.c[inv_field]==invoice_id)).mappings().first()
    rid=old['id'] if old else str(uuid.uuid4())
    if old:c.execute(table.update().where(table.c.id==rid).values(amount=old['amount']+amount))
    else:c.execute(table.insert().values(id=rid,organization_id=p.organization_id,**{pay_field:payment_id,inv_field:invoice_id},amount=amount,created_by=p.user_id,created_at=utcnow()))
    c.execute(events.insert().values(id=str(uuid.uuid4()),organization_id=p.organization_id,**{'supplier_allocation_id' if supplier else 'customer_allocation_id':rid},amount=amount,occurred_at=utcnow(),actor_user_id=p.user_id))
    remaining=invoice['total_amount']-used-amount
    c.execute(md.tables[invoice_table].update().where(md.tables[invoice_table].c.id==invoice_id).values(status='paid' if remaining==0 else 'partially_paid',updated_at=utcnow()))
    if not supplier:rebuild_debt(c,p.organization_id,invoice['customer_id'])
    audit(c,p,'allocate_payment',table.name,rid,{'increment':amount,'payment_id':payment_id,'invoice_id':invoice_id})
    return {'id':rid,'invoice_remaining':remaining,'payment_remaining':payment['amount']-paid-amount}

@router.post('/customer-receipts/{row_id}/allocations')
def allocate_receipt(row_id:str,b:Allocation,request:Request):
    return perform(request,'finance.write',b,lambda c,p,key:allocate(c,p,row_id,str(b.invoice_id),b.amount))

@router.post('/supplier-bills/{row_id}/post')
def post_bill(row_id:str,b:Empty,request:Request):
    return perform(request,'finance.write',b,lambda c,p,key:transition(c,p,'supplier_bills',row_id,'finance.write',{'draft'},'posted'))

@router.post('/supplier-payments/{row_id}/verify')
def verify_payment(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        row=get(c,'supplier_payments',row_id,p,'finance.write')
        if row['amount']<=0:raise HTTPException(422,'Số tiền phải lớn hơn 0')
        result=transition(c,p,'supplier_payments',row_id,'finance.write',{'draft'},'verified')
        c.execute(md.tables['supplier_payments'].update().where(md.tables['supplier_payments'].c.id==row_id).values(paid_at=utcnow()))
        return result
    return perform(request,'finance.write',b,run)

@router.post('/supplier-payments/{row_id}/allocations')
def allocate_payment(row_id:str,b:SupplierAllocation,request:Request):
    return perform(request,'finance.write',b,lambda c,p,key:allocate(c,p,row_id,str(b.bill_id),b.amount,True))

@router.get('/customers/{row_id}/debt-reconciliation')
def reconciliation(row_id:str,request:Request):
    from backend.app.core.security import current
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('finance.read');customer=get(c,'customers',row_id,p,'finance.read')
        derived=rebuild_debt(c,p.organization_id,row_id,False)
        return {'customer_id':row_id,'previous_cache':customer['current_debt_amount'],'derived_amount':derived,'reconciled':derived==customer['current_debt_amount']}

@router.post('/customers/{row_id}/rebuild-debt')
def rebuild_customer_debt(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        get(c,'customers',row_id,p,'finance.write')
        result=rebuild_debt(c,p.organization_id,row_id)
        audit(c,p,'rebuild_debt','customers',row_id,{'derived_amount':result})
        return {'customer_id':row_id,'derived_amount':result}
    return perform(request,'finance.write',b,run)
