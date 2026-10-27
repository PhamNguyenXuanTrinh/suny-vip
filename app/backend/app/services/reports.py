from datetime import date,datetime,time,timedelta,timezone
from decimal import Decimal
import sqlalchemy as sa
from fastapi import APIRouter,Request,HTTPException
from backend.app.models import metadata as md
from backend.app.models.base import utcnow
from backend.app.core.clock import business_today,business_zone,day_start_utc
from backend.app.core.security import current
from backend.app.core.tenancy import scope
from backend.app.services.data import serialize,money
from backend.app.services.finance import events,supplier_allocations

from backend.app.schemas.reporting import AgingReport,InventoryReport,ProductionReport,DashboardReport,CashReport,KPIReport

def paging(page,page_size):
    if page<1 or not 1<=page_size<=100:raise HTTPException(422,'Phân trang không hợp lệ')

router=APIRouter(prefix='/api/v1',tags=['Management reports and KPI'])

def aging(c,p,as_of,supplier=False,page=1,page_size=100):
    paging(page,page_size)
    permission='reports.read';p.require(permission)
    name='supplier_bills' if supplier else 'customer_invoices';t=md.tables[name]
    allocations=supplier_allocations if supplier else md.tables['customer_payment_allocations']
    fk='bill_id' if supplier else 'invoice_id';ef='supplier_allocation_id' if supplier else 'customer_allocation_id'
    day_field='bill_date' if supplier else 'invoice_date';party='supplier_id' if supplier else 'customer_id'
    parties=md.tables['suppliers' if supplier else 'customers']
    active=['posted','partially_paid','paid'] if supplier else ['issued','partially_paid','paid','overdue']
    rows=c.execute(sa.select(t).where(scope(name,p,permission),t.c[day_field]<=as_of,t.c.status.in_(active))).mappings().all()
    cutoff=day_start_utc(as_of+timedelta(days=1))
    summary={'not_due':0,'days_1_30':0,'days_31_60':0,'days_61_90':0,'days_over_90':0};items=[]
    for r in rows:
        paid=c.execute(sa.select(sa.func.coalesce(sa.func.sum(events.c.amount),0)).select_from(events.join(allocations,allocations.c.id==events.c[ef])).where(allocations.c[fk]==r['id'],events.c.organization_id==p.organization_id,events.c.occurred_at<cutoff)).scalar_one()
        outstanding=r['total_amount']-paid
        if outstanding<=0:continue
        days=max((as_of-(r['due_date'] or r[day_field])).days,0)
        bucket='not_due' if days==0 else 'days_1_30' if days<=30 else 'days_31_60' if days<=60 else 'days_61_90' if days<=90 else 'days_over_90'
        party_name=c.execute(sa.select(parties.c.name).where(parties.c.id==r[party])).scalar_one()
        summary[bucket]+=outstanding
        items.append({'id':r['id'],'party_id':r[party],'party_name':party_name,'reference':r['bill_no' if supplier else 'invoice_no'],'due_date':(r['due_date'] or r[day_field]).isoformat(),'total_amount':r['total_amount'],'allocated_amount':paid,'outstanding_amount':outstanding,'overdue_days':days,'bucket':bucket})
    return {'items':items[(page-1)*page_size:page*page_size],'page':page,'page_size':page_size,'total_items':len(items),'total_outstanding':sum(summary.values()),'buckets':summary,'as_of':as_of.isoformat(),'timezone':business_zone().key,'currency':'VND','source_tables':[name,allocations.name,'payment_allocation_events'],'generated_at':utcnow().isoformat()}

def inventory_summary(c,p,page=1,page_size=100):
    paging(page,page_size)
    p.require('inventory.read');t=md.tables['inventory_units']
    rows=c.execute(sa.select(t).where(scope('inventory_units',p,'inventory.read'))).mappings().all()
    groups={};total=0
    for r in rows:
        k=(r['product_id'],r['warehouse_id'],r['uom']);g=groups.setdefault(k,{'product_id':k[0],'warehouse_id':k[1],'uom':k[2],'quantity':Decimal(0),'value_vnd':0})
        g['quantity']+=r['remaining_quantity'];value=money(r['remaining_quantity']*r['unit_cost']);g['value_vnd']+=value;total+=value
    transfers=md.tables['stock_transfers'];lines=md.tables['stock_transfer_lines'];units=md.tables['inventory_units']
    in_transit=c.execute(sa.select(lines.c.quantity,units.c.unit_cost).join(transfers,transfers.c.id==lines.c.transfer_id).join(units,units.c.id==lines.c.inventory_unit_id).where(scope('stock_transfers',p,'inventory.read'),transfers.c.status=='shipped')).all()
    transit_value=sum(money(q*cost) for q,cost in in_transit)
    return {'items':[serialize(g) for g in groups.values()][(page-1)*page_size:page*page_size],'page':page,'page_size':page_size,'total_groups':len(groups),'on_hand_value_vnd':total,'in_transit_value_vnd':transit_value,'total_value_vnd':total+transit_value,'currency':'VND','valuation':'unit_cost per inventory unit; in-transit transfers included separately','source_tables':['inventory_units','inventory_movements','stock_transfers','stock_transfer_lines'],'generated_at':utcnow().isoformat()}

def production_summary(c,p,start=None,end=None,page=1,page_size=100):
    paging(page,page_size)
    p.require('production.read');t=md.tables['production_orders'];q=sa.select(t).where(scope('production_orders',p,'production.read'))
    if start:q=q.where(t.c.created_at>=day_start_utc(start))
    if end:q=q.where(t.c.created_at<day_start_utc(end+timedelta(days=1)))
    rows=c.execute(q.order_by(t.c.created_at.desc())).mappings().all()
    by_unit={};report_rows=[];total_downtime=0
    products=md.tables['products']
    for r in rows:
        reports=md.tables['production_reports']
        downtime=c.execute(sa.select(sa.func.coalesce(sa.func.sum(reports.c.downtime_minutes),0)).where(reports.c.organization_id==p.organization_id,reports.c.production_order_id==r['id'])).scalar_one()
        total_downtime+=downtime;report_rows.append({**serialize(r),'downtime_minutes':downtime})
        unit=c.execute(sa.select(products.c.base_uom).where(products.c.id==r['product_id'])).scalar_one()
        g=by_unit.setdefault(unit,{'uom':unit,'planned_quantity':Decimal(0),'good_quantity':Decimal(0),'scrap_quantity':Decimal(0)})
        for field in ('planned_quantity','good_quantity','scrap_quantity'):g[field]+=r[field]
    return {'items':report_rows[(page-1)*page_size:page*page_size],'page':page,'page_size':page_size,'total_orders':len(rows),'total_downtime_minutes':total_downtime,'totals_by_uom':[serialize(v) for v in by_unit.values()],'source_tables':['production_orders','production_reports'],'generated_at':utcnow().isoformat()}

def kpi_progress(c,p,period_start=None,period_end=None,page=1,page_size=100):
    paging(page,page_size)
    p.require('kpi.read');t=md.tables['kpi_targets'];results=[]
    clauses=[scope('kpi_targets',p,'kpi.read')]
    if period_start:clauses.append(t.c.period_start==period_start)
    if period_end:clauses.append(t.c.period_end==period_end)
    total_items=c.execute(sa.select(sa.func.count()).select_from(t).where(*clauses)).scalar_one()
    for r in c.execute(sa.select(t).where(*clauses).order_by(t.c.period_start.desc(),t.c.id).offset((page-1)*page_size).limit(page_size)).mappings():
        actual=Decimal(0);sources=[];unit='VND' if r['kpi_type']=='sales_revenue' else '%' if r['kpi_type'] in ('scrap_rate','task_completion') else 'm2'
        if r['kpi_type']=='sales_revenue':
            i=md.tables['customer_invoices'];customers=md.tables['customers']
            actual=Decimal(c.execute(sa.select(sa.func.coalesce(sa.func.sum(i.c.subtotal_amount),0)).join(customers,customers.c.id==i.c.customer_id).where(i.c.organization_id==p.organization_id,customers.c.owner_employee_id==r['employee_id'],i.c.invoice_date>=r['period_start'],i.c.invoice_date<=r['period_end'],i.c.status.in_(['issued','partially_paid','paid','overdue']))).scalar_one());sources=['customer_invoices','customers']
        elif r['kpi_type'] in ('output_quantity','scrap_rate'):
            reports=md.tables['production_reports'];users=md.tables['app_users'];orders=md.tables['production_orders'];products=md.tables['products'];ops=md.tables['production_order_operations']
            final=sa.select(sa.func.max(ops.c.sequence_no)).where(ops.c.production_order_id==orders.c.id).correlate(orders).scalar_subquery()
            q=sa.select(reports.c.good_quantity,reports.c.scrap_quantity,reports.c.id).join(users,users.c.id==reports.c.reported_by).join(orders,orders.c.id==reports.c.production_order_id).join(products,products.c.id==orders.c.product_id).join(ops,ops.c.id==reports.c.operation_id).where(reports.c.organization_id==p.organization_id,users.c.employee_id==r['employee_id'],products.c.base_uom=='m2',ops.c.sequence_no==final,reports.c.reported_at>=day_start_utc(r['period_start']),reports.c.reported_at<day_start_utc(r['period_end']+timedelta(days=1)))
            values=c.execute(q).all();good=sum((v[0] for v in values),Decimal(0));scrap=sum((v[1] for v in values),Decimal(0))
            actual=good if r['kpi_type']=='output_quantity' else scrap*100/(good+scrap) if good+scrap else Decimal(0);sources=['production_reports','production_order_operations','products'];
            if values:
                fixes=md.tables['production_report_corrections'];deltas=c.execute(sa.select(fixes.c.good_delta,fixes.c.scrap_delta).where(fixes.c.organization_id==p.organization_id,fixes.c.report_id.in_([v[2] for v in values]))).all()
                good+=sum((v[0] for v in deltas),Decimal(0));scrap+=sum((v[1] for v in deltas),Decimal(0))
                actual=good if r['kpi_type']=='output_quantity' else scrap*100/(good+scrap) if good+scrap else Decimal(0)
                sources.append('production_report_corrections')
        else:
            tasks=md.tables['tasks'];ass=md.tables['task_assignees']
            statuses=c.execute(sa.select(tasks.c.status).join(ass,ass.c.task_id==tasks.c.id).where(tasks.c.organization_id==p.organization_id,ass.c.employee_id==r['employee_id'],ass.c.status!='removed',tasks.c.due_at>=day_start_utc(r['period_start']),tasks.c.due_at<day_start_utc(r['period_end']+timedelta(days=1)))).scalars().all()
            actual=Decimal(sum(s=='completed' for s in statuses))*100/len(statuses) if statuses else Decimal(0);sources=['tasks','task_assignees']
        target=Decimal(r['target_amount'] if r['target_amount'] is not None else r['target_value'])
        achieved=actual<=target if r['kpi_type']=='scrap_rate' else actual>=target
        results.append({**serialize(r),'actual_value':str(actual.quantize(Decimal('0.000001'))),'unit':unit,'achieved':achieved,'direction':'at_most' if r['kpi_type']=='scrap_rate' else 'at_least','source_tables':sources,'scope_note':'Output and scrap KPI include final-operation reports for products measured in m2' if unit in ('m2','%') and r['kpi_type']!='task_completion' else None})
    return {'items':results,'page':page,'page_size':page_size,'total_items':total_items,'generated_at':utcnow().isoformat(),'source':'business_records'}

def dashboard_money(c,p):
    p.require('reports.read');day=business_today(utcnow());invoices=md.tables['customer_invoices']
    revenue=c.execute(sa.select(sa.func.coalesce(sa.func.sum(invoices.c.subtotal_amount),0)).where(scope('customer_invoices',p,'reports.read'),invoices.c.invoice_date<=day,invoices.c.status.in_(['issued','partially_paid','paid','overdue']))).scalar_one()
    ar=aging(c,p,day);ap=aging(c,p,day,True);stock=inventory_summary(c,p)
    return {'revenue_vnd':revenue,'receivables_vnd':ar['total_outstanding'],'payables_vnd':ap['total_outstanding'],'inventory_value_vnd':stock['total_value_vnd'],'as_of':day.isoformat(),'currency':'VND','definitions':{'revenue':'Issued business invoices before VAT through the report date; excludes cancelled/draft invoices','receivables':'Invoice balances after allocation events; customer advances are not subtracted until allocated','inventory':'On-hand unit cost plus goods in transit'},'source_tables':['customer_invoices','supplier_bills','payment_allocation_events','inventory_movements','inventory_units'],'generated_at':utcnow().isoformat()}

def cashflow_forecast(c,p,days=30):
    p.require('reports.read')
    if not 1<=days<=365:raise HTTPException(422,'Số ngày dự kiến cần từ 1 đến 365')
    today=business_today(utcnow());last=today+timedelta(days=days-1)
    rows={today+timedelta(days=i):{'date':(today+timedelta(days=i)).isoformat(),'expected_receipts_vnd':0,'expected_payments_vnd':0,'net_vnd':0} for i in range(days)}
    from backend.app.services.finance import allocated
    for supplier in (False,True):
        table_name='supplier_bills' if supplier else 'customer_invoices';t=md.tables[table_name];alloc=supplier_allocations if supplier else md.tables['customer_payment_allocations'];key='bill_id' if supplier else 'invoice_id'
        states=['posted','partially_paid'] if supplier else ['issued','partially_paid','overdue']
        source=c.execute(sa.select(t).where(scope(table_name,p,'reports.read'),t.c.status.in_(states))).mappings().all()
        for item in source:
            due=item['due_date'] or item['bill_date' if supplier else 'invoice_date'];due=max(today,due)
            if due>last:continue
            outstanding=item['total_amount']-allocated(c,alloc,key,item['id'])
            rows[due]['expected_payments_vnd' if supplier else 'expected_receipts_vnd']+=outstanding
    for item in rows.values():item['net_vnd']=item['expected_receipts_vnd']-item['expected_payments_vnd']
    return {'items':list(rows.values()),'total_expected_net_vnd':sum(r['net_vnd'] for r in rows.values()),'currency':'VND','as_of':today.isoformat(),'opening_cash_balance':None,'note':'Dự kiến theo hạn chứng từ AR/AP, chưa bao gồm lương, chi phí chưa có chứng từ và số dư tiền đầu kỳ; không phải cam kết thu hoặc chi tiền.','source_tables':['customer_invoices','supplier_bills','customer_payment_allocations','supplier_payment_allocations'],'generated_at':utcnow().isoformat()}

@router.get('/reports/dashboard-money',response_model=DashboardReport)
def dashboard(request:Request):
    with request.app.state.engine.begin() as c:return dashboard_money(c,current(c,request))
@router.get('/reports/ar-aging',response_model=AgingReport)
def ar(request:Request,as_of:date|None=None,page:int=1,page_size:int=25):
    with request.app.state.engine.begin() as c:return aging(c,current(c,request),as_of or business_today(utcnow()),page=page,page_size=page_size)
@router.get('/reports/ap-aging',response_model=AgingReport)
def ap(request:Request,as_of:date|None=None,page:int=1,page_size:int=25):
    with request.app.state.engine.begin() as c:return aging(c,current(c,request),as_of or business_today(utcnow()),True,page=page,page_size=page_size)
@router.get('/reports/inventory',response_model=InventoryReport)
def inventory(request:Request,page:int=1,page_size:int=25):
    with request.app.state.engine.begin() as c:return inventory_summary(c,current(c,request),page,page_size)
@router.get('/reports/production',response_model=ProductionReport)
def production(request:Request,start:date|None=None,end:date|None=None,page:int=1,page_size:int=25):
    if start and end and start>end:raise HTTPException(422,'Kỳ báo cáo không hợp lệ')
    with request.app.state.engine.begin() as c:return production_summary(c,current(c,request),start,end,page,page_size)
@router.get('/kpi-progress',response_model=KPIReport)
def kpi(request:Request,period_start:date|None=None,period_end:date|None=None,page:int=1,page_size:int=100):
    with request.app.state.engine.begin() as c:return kpi_progress(c,current(c,request),period_start,period_end,page,page_size)

@router.get('/reports/cashflow-forecast',response_model=CashReport)
def forecast(request:Request,days:int=30):
    with request.app.state.engine.begin() as c:return cashflow_forecast(c,current(c,request),days)

@router.patch('/notifications/{row_id}/read')
@router.post('/notifications/{row_id}/read')
def read_notification(row_id:str,request:Request):
    from backend.app.services.data import get
    with request.app.state.engine.begin() as c:
        p=current(c,request);get(c,'notifications',row_id,p,'session.read');t=md.tables['notifications']
        c.execute(t.update().where(t.c.id==row_id).values(is_read=True,read_at=utcnow()))
    return {'id':row_id,'is_read':True}
