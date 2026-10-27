"""One query scope reused by list, detail, writes, reports and AI tools."""
import sqlalchemy as sa
from backend.app.models import metadata as md

PARENTS={
 'customer_contacts':('customer_id','customers'),'sales_order_lines':('order_id','sales_orders'),
 'shipment_lines':('shipment_id','shipments'),'purchase_order_lines':('purchase_order_id','purchase_orders'),
 'warehouse_locations':('warehouse_id','warehouses'),'bom_lines':('bom_id','bills_of_materials'),
 'production_order_operations':('production_order_id','production_orders'),'production_reports':('production_order_id','production_orders'),
 'stock_transfer_lines':('transfer_id','stock_transfers'),'task_assignees':('task_id','tasks'),'task_updates':('task_id','tasks'),
 'customer_invoice_lines':('invoice_id','customer_invoices'),'customer_payment_allocations':('invoice_id','customer_invoices'),
}

def employee_ids(p,site_id):
    e=md.tables['employees']
    return sa.select(e.c.id).where(e.c.organization_id==p.organization_id,e.c.site_id==site_id).correlate_except(e)

def production_at_site(t,p,site_id):
    op=md.tables['production_order_operations'];wc=md.tables['work_centers']
    at=sa.select(op.c.production_order_id).join(wc,wc.c.id==op.c.work_center_id).where(wc.c.organization_id==p.organization_id,wc.c.site_id==site_id).correlate_except(op,wc)
    outside=sa.select(op.c.production_order_id).join(wc,wc.c.id==op.c.work_center_id).where(wc.c.organization_id==p.organization_id,wc.c.site_id!=site_id).correlate_except(op,wc)
    return sa.and_(t.c.id.in_(at),t.c.id.not_in(outside))

def one_grant(table_name,p,g):
    """Keep ownership and site constraints paired with the grant that permits them."""
    t=md.tables[table_name];clauses=[t.c.organization_id==p.organization_id]
    site=g['site_id'];role=g['code']
    if table_name in PARENTS:
        field,parent=PARENTS[table_name];pt=md.tables[parent]
        clauses.append(t.c[field].in_(sa.select(pt.c.id).where(one_grant(parent,p,g)).correlate_except(pt)))
        return sa.and_(*clauses)
    if table_name=='customers':
        if role=='CTV':clauses.append(t.c.owner_employee_id==p.employee_id)
        if site:clauses.append(t.c.owner_employee_id.in_(employee_ids(p,site)))
    elif table_name in ('sales_orders','shipments','customer_invoices','customer_receipts'):
        parent=md.tables['customers'];clauses.append(t.c.customer_id.in_(sa.select(parent.c.id).where(one_grant('customers',p,g)).correlate_except(parent)))
    elif table_name=='notifications':
        if not (role=='ADMIN' and site is None):clauses.append(t.c.user_id==p.user_id)
    elif table_name=='kpi_targets':
        if role!='ADMIN':clauses.append(t.c.employee_id==p.employee_id)
        if site:clauses.append(t.c.employee_id.in_(employee_ids(p,site)))
    elif table_name=='tasks':
        ass=md.tables['task_assignees'];users=md.tables['app_users']
        assigned=sa.select(ass.c.task_id).where(ass.c.organization_id==p.organization_id,ass.c.employee_id==p.employee_id,ass.c.status!='removed').correlate_except(ass)
        if role!='ADMIN':clauses.append(sa.or_(t.c.created_by==p.user_id,t.c.id.in_(assigned)))
        if site:
            orders=md.tables['production_orders']
            production=sa.select(orders.c.id).where(orders.c.organization_id==p.organization_id,production_at_site(orders,p,site)).correlate_except(orders)
            local_users=sa.select(users.c.id).where(users.c.organization_id==p.organization_id,users.c.employee_id.in_(employee_ids(p,site))).correlate_except(users)
            local_tasks=sa.select(ass.c.task_id).where(ass.c.organization_id==p.organization_id,ass.c.employee_id.in_(employee_ids(p,site)),ass.c.status!='removed').correlate_except(ass)
            clauses.append(sa.or_(t.c.production_order_id.in_(production),sa.and_(t.c.production_order_id.is_(None),sa.or_(t.c.created_by.in_(local_users),t.c.id.in_(local_tasks)))))
    elif table_name=='production_orders':
        if role=='WORKER':
            tasks=md.tables['tasks'];assign=md.tables['task_assignees']
            clauses.append(t.c.id.in_(sa.select(tasks.c.production_order_id).join(assign,assign.c.task_id==tasks.c.id).where(tasks.c.organization_id==p.organization_id,assign.c.organization_id==p.organization_id,assign.c.employee_id==p.employee_id,assign.c.status!='removed',tasks.c.status!='cancelled').correlate_except(tasks,assign)))
        if site:clauses.append(production_at_site(t,p,site))
    elif table_name=='employees' and role=='CTV':
        clauses.append(t.c.id==p.employee_id)
        if site:clauses.append(t.c.site_id==site)
    elif site:
        if table_name=='sites':clauses.append(t.c.id==site)
        elif table_name in ('employees','warehouses','work_centers'):clauses.append(t.c.site_id==site)
        elif table_name=='machines':
            wc=md.tables['work_centers'];clauses.append(t.c.work_center_id.in_(sa.select(wc.c.id).where(wc.c.organization_id==p.organization_id,wc.c.site_id==site).correlate_except(wc)))
        elif table_name in ('inventory_units','inventory_movements','stock_transfers'):
            wh=md.tables['warehouses'];visible=sa.select(wh.c.id).where(wh.c.organization_id==p.organization_id,wh.c.site_id==site).correlate_except(wh)
            if table_name=='stock_transfers':clauses.append(sa.and_(t.c.from_warehouse_id.in_(visible),t.c.to_warehouse_id.in_(visible)))
            else:clauses.append(t.c.warehouse_id.in_(visible))
        elif table_name not in ('products','bills_of_materials','inventory_lots','roles'):clauses.append(sa.false())
    return sa.and_(*clauses)

def scope(table_name,p,permission):
    if permission=='session.read':
        t=md.tables[table_name]
        return sa.and_(t.c.organization_id==p.organization_id,sa.true() if p.is_global_admin else t.c.user_id==p.user_id)
    return sa.or_(*(one_grant(table_name,p,g) for g in p.matching_grants(permission)))
