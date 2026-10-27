from decimal import Decimal
from uuid import UUID
import sqlalchemy as sa
from fastapi import APIRouter,Request,HTTPException
from pydantic import Field
from backend.app.models import metadata as md
from backend.app.models.base import utcnow,UTCDateTime,Quantity
from backend.app.services.data import get,money
from backend.app.services.inventory import Input,Ship,movement,receive_unit
from backend.app.services.workflows import perform,Empty,transition
from backend.app.services.auth import audit

from backend.app.schemas.common import PostingRouter
router=PostingRouter(prefix='/api/v1',tags=['Production and work assignments'])
corrections=sa.Table('production_report_corrections',md,
    sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),nullable=False),sa.Column('report_id',sa.String(36),nullable=False),sa.Column('good_delta',Quantity(),nullable=False),sa.Column('scrap_delta',Quantity(),nullable=False),sa.Column('reason',sa.Text,nullable=False),sa.Column('actor_user_id',sa.String(36),nullable=False),sa.Column('created_at',UTCDateTime(),nullable=False))
corrections.append_constraint(sa.ForeignKeyConstraint(['organization_id','report_id'],['production_reports.organization_id','production_reports.id']))
corrections.append_constraint(sa.ForeignKeyConstraint(['organization_id','actor_user_id'],['app_users.organization_id','app_users.id']))
sa.Index('ix_production_corrections_report',corrections.c.report_id)

class Correction(Input):
    good_delta:Decimal=Field(default=Decimal(0),max_digits=18,decimal_places=6)
    scrap_delta:Decimal=Field(default=Decimal(0),max_digits=18,decimal_places=6)
    reason:str=Field(min_length=8,max_length=2000)

class Report(Input):
    operation_id:UUID
    good_quantity:Decimal=Field(default=Decimal(0),ge=0,max_digits=18,decimal_places=6)
    scrap_quantity:Decimal=Field(default=Decimal(0),ge=0,max_digits=18,decimal_places=6)
    downtime_minutes:int=Field(default=0,strict=True,ge=0,le=1440)
    downtime_reason:str|None=Field(default=None,max_length=120)
    notes:str|None=Field(default=None,max_length=4000)
class TaskUpdate(Input):
    status:str=Field(pattern='^(open|in_progress|blocked|completed|cancelled)$')
    content:str=Field(min_length=1,max_length=4000)
    progress_percent:int=Field(strict=True,ge=0,le=100)

def material_cost(c,org,order_id):
    movements=md.tables['inventory_movements']
    return c.execute(sa.select(sa.func.coalesce(sa.func.sum(movements.c.total_value),0)).where(movements.c.organization_id==org,movements.c.reference_type=='production_order',movements.c.reference_id==order_id,movements.c.movement_type=='production_consume')).scalar_one()

def operation_totals(c,org,operation_id):
    reports=md.tables['production_reports']
    rows=c.execute(sa.select(reports.c.good_quantity,reports.c.scrap_quantity).where(reports.c.organization_id==org,reports.c.operation_id==operation_id)).all()
    fixes=c.execute(sa.select(corrections.c.good_delta,corrections.c.scrap_delta).join(reports,reports.c.id==corrections.c.report_id).where(reports.c.organization_id==org,reports.c.operation_id==operation_id)).all()
    return tuple(sum((r[i] for r in rows),Decimal(0))+sum((r[i] for r in fixes),Decimal(0)) for i in (0,1))

def operation_capacity(c,p,order,operations,index):
    return order['released_quantity'] if index==0 else operation_totals(c,p.organization_id,operations[index-1]['id'])[0]

def refresh_order_totals(c,p,order_id,operations):
    totals=[operation_totals(c,p.organization_id,o['id']) for o in operations]
    good=totals[-1][0];scrap=sum((r[1] for r in totals),Decimal(0))
    c.execute(md.tables['production_orders'].update().where(md.tables['production_orders'].c.id==order_id).values(good_quantity=good,scrap_quantity=scrap,updated_at=utcnow()))

def refresh_following_operations(c,p,operations):
    table=md.tables['production_order_operations']
    for index in range(1,len(operations)):
        previous=c.execute(sa.select(table).where(table.c.id==operations[index-1]['id'])).mappings().one()
        current=c.execute(sa.select(table).where(table.c.id==operations[index]['id'])).mappings().one()
        good,_=operation_totals(c,p.organization_id,previous['id'])
        reports=md.tables['production_reports']
        has_report=c.execute(sa.select(reports.c.id).where(reports.c.organization_id==p.organization_id,reports.c.operation_id==current['id'])).first()
        if has_report:continue
        status='pending' if previous['status']!='completed' else 'completed' if good==0 else 'ready'
        if current['status']!=status:
            c.execute(table.update().where(table.c.id==current['id']).values(status=status,actual_start_at=None,actual_end_at=utcnow() if status=='completed' else None,updated_at=utcnow()))
            audit(c,p,'no_input_operation_closed' if status=='completed' else 'operation_readied','production_order_operations',current['id'],{'input_good_quantity':str(good),'reason':'No usable output remains from previous operation' if status=='completed' else 'Previous operation output updated'})

def bom_cycle(c,org,product_id,bom_id):
    b=md.tables['bills_of_materials'];l=md.tables['bom_lines'];graph={}
    rows=c.execute(sa.select(b.c.product_id,l.c.component_product_id).join(l,l.c.bom_id==b.c.id).where(b.c.organization_id==org,sa.or_(b.c.status=='active',b.c.id==bom_id))).all()
    for product,component in rows:graph.setdefault(product,set()).add(component)
    def visit(node,chain):
        if node in chain:return True
        return any(visit(child,chain|{node}) for child in graph.get(node,set()))
    return visit(product_id,set())

@router.post('/boms/{row_id}/activate')
def activate(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        bom=get(c,'bills_of_materials',row_id,p,'production.write');l=md.tables['bom_lines']
        if bom['status']!='draft':raise HTTPException(409,'Chỉ kích hoạt BOM nháp')
        if bom['output_quantity']<=0:raise HTTPException(422,'Sản lượng định mức phải lớn hơn 0')
        if c.execute(sa.select(l.c.id).where(l.c.bom_id==row_id,sa.or_(l.c.quantity<=0,l.c.scrap_rate>10000))).first():raise HTTPException(422,'Định mức nguyên liệu hoặc hao hụt không hợp lệ')
        if not c.execute(sa.select(l.c.id).where(l.c.bom_id==row_id)).first():raise HTTPException(409,'BOM chưa có nguyên vật liệu')
        if bom_cycle(c,p.organization_id,bom['product_id'],row_id):raise HTTPException(422,'Định mức tạo thành vòng lặp')
        return transition(c,p,'bills_of_materials',row_id,'production.write',{'draft'},'active')
    return perform(request,'production.write',b,run)

@router.post('/production-orders/{row_id}/release')
def release(row_id:str,b:Ship,request:Request):
    def run(c,p,key):
        order=get(c,'production_orders',row_id,p,'production.write');bom=get(c,'bills_of_materials',order['bom_id'],p,'production.write')
        if order['status']!='draft' or bom['status']!='active':raise HTTPException(409,'Lệnh phải là nháp và BOM phải đang hoạt động')
        if order['planned_quantity']<=0 or bom['output_quantity']<=0:raise HTTPException(422,'Số lượng sản xuất và định mức phải lớn hơn 0')
        get(c,'warehouses',str(b.warehouse_id),p,'inventory.write')
        ops=md.tables['production_order_operations'];materials=md.tables['bom_lines'];units=md.tables['inventory_units']
        operations=c.execute(sa.select(ops).where(ops.c.production_order_id==row_id).order_by(ops.c.sequence_no)).mappings().all()
        if not operations:raise HTTPException(409,'Lệnh chưa có công đoạn sản xuất')
        components=c.execute(sa.select(materials).where(materials.c.bom_id==bom['id'])).mappings().all()
        for component in components:
            required=component['quantity']*order['planned_quantity']/bom['output_quantity']*(Decimal(10000)+component['scrap_rate'])/10000
            required=required.quantize(Decimal('0.000001'),rounding='ROUND_CEILING')
            rows=c.execute(sa.select(units).where(units.c.organization_id==p.organization_id,units.c.warehouse_id==str(b.warehouse_id),units.c.product_id==component['component_product_id'],units.c.status=='available',units.c.remaining_quantity>0).order_by(units.c.received_at,units.c.id)).mappings().all()
            need=required
            for unit in rows:
                take=min(need,unit['remaining_quantity'])
                if take>0:movement(c,p,unit['id'],-take,'production_consume',key,component['id']+unit['id'],'production_order',row_id)
                need-=take
                if need==0:break
            if need>0:raise HTTPException(409,'Thiếu nguyên vật liệu theo định mức; chưa phát hành lệnh')
        c.execute(md.tables['production_orders'].update().where(md.tables['production_orders'].c.id==row_id).values(status='released',released_quantity=order['planned_quantity'],updated_at=utcnow()))
        c.execute(ops.update().where(ops.c.id==operations[0]['id']).values(status='ready',updated_at=utcnow()))
        audit(c,p,'release_and_consume_materials','production_orders',row_id)
        return {'id':row_id,'status':'released','released_quantity':str(order['planned_quantity'])}
    return perform(request,'production.write',b,run)

@router.post('/production-orders/{row_id}/start')
def start(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        order=get(c,'production_orders',row_id,p,'production.report')
        if order['status']!='released':raise HTTPException(409,'Lệnh chưa được phát hành hoặc đã bắt đầu')
        c.execute(md.tables['production_orders'].update().where(md.tables['production_orders'].c.id==row_id).values(status='in_progress',actual_start_at=utcnow(),updated_at=utcnow()))
        ops=md.tables['production_order_operations']
        c.execute(ops.update().where(ops.c.production_order_id==row_id,ops.c.status=='ready').values(status='in_progress',actual_start_at=utcnow(),updated_at=utcnow()))
        audit(c,p,'start','production_orders',row_id)
        return {'id':row_id,'status':'in_progress'}
    return perform(request,'production.report',b,run)

@router.post('/production-orders/{row_id}/reports')
def report(row_id:str,b:Report,request:Request):
    def run(c,p,key):
        order=get(c,'production_orders',row_id,p,'production.report');ops=md.tables['production_order_operations'];reports=md.tables['production_reports']
        if order['status']!='in_progress':raise HTTPException(409,'Chỉ báo cáo cho lệnh đang sản xuất')
        operations=c.execute(sa.select(ops).where(ops.c.production_order_id==row_id).order_by(ops.c.sequence_no)).mappings().all()
        index=next((i for i,o in enumerate(operations) if o['id']==str(b.operation_id)),None)
        if index is None:raise HTTPException(404,'Công đoạn không thuộc lệnh sản xuất')
        if index>0 and operations[index-1]['status']!='completed':raise HTTPException(409,'Công đoạn trước chưa hoàn thành')
        if operations[index]['status']=='completed':raise HTTPException(409,'Công đoạn đã hoàn thành')
        if b.good_quantity+b.scrap_quantity==0 and b.downtime_minutes==0:raise HTTPException(422,'Báo cáo chưa có số liệu')
        if b.downtime_minutes and not b.downtime_reason:raise HTTPException(422,'Cần ghi lý do dừng máy')
        good,scrap=operation_totals(c,p.organization_id,str(b.operation_id))
        good+=b.good_quantity;scrap+=b.scrap_quantity
        capacity=operation_capacity(c,p,order,operations,index)
        if good+scrap>capacity:raise HTTPException(409,'Sản lượng vượt lượng đạt được chuyển từ công đoạn trước')
        consumed=material_cost(c,p.organization_id,row_id)
        cost_per_planned=Decimal(consumed)/order['released_quantity']
        rid=str(__import__('uuid').uuid4())
        c.execute(reports.insert().values(id=rid,organization_id=p.organization_id,production_order_id=row_id,operation_id=str(b.operation_id),reported_by=p.user_id,good_quantity=b.good_quantity,scrap_quantity=b.scrap_quantity,scrap_value=money(b.scrap_quantity*cost_per_planned),downtime_minutes=b.downtime_minutes,downtime_reason=b.downtime_reason,notes=b.notes))
        done=good+scrap==capacity
        c.execute(ops.update().where(ops.c.id==str(b.operation_id)).values(status='completed' if done else 'in_progress',actual_start_at=operations[index]['actual_start_at'] or utcnow(),actual_end_at=utcnow() if done else None,updated_at=utcnow()))
        refresh_following_operations(c,p,operations)
        refresh_order_totals(c,p,row_id,operations)
        audit(c,p,'production_report','production_reports',rid)
        return {'id':rid,'operation_status':'completed' if done else 'in_progress','final_operation':index==len(operations)-1}
    return perform(request,'production.report',b,run)

@router.post('/production-reports/{row_id}/corrections')
def correct_report(row_id:str,b:Correction,request:Request):
    def run(c,p,key):
        report=get(c,'production_reports',row_id,p,'production.write');order=get(c,'production_orders',report['production_order_id'],p,'production.write')
        if order['status']!='in_progress':raise HTTPException(409,'Chỉ đính chính trước khi lệnh hoàn tất và ghi sổ thành phẩm')
        if b.good_delta==0 and b.scrap_delta==0:raise HTTPException(422,'Chưa có số lượng đính chính')
        op=md.tables['production_order_operations'];reports=md.tables['production_reports'];operation=get(c,'production_order_operations',report['operation_id'],p,'production.write')
        later=c.execute(sa.select(reports.c.id).join(op,op.c.id==reports.c.operation_id).where(op.c.production_order_id==order['id'],op.c.sequence_no>operation['sequence_no'])).first()
        if later:raise HTTPException(409,'Công đoạn tiếp theo đã có báo cáo; cần đối soát trước khi đính chính công đoạn nguồn')
        # A correction is tied to one immutable report and cannot make that report negative.
        original_fixes=c.execute(sa.select(corrections.c.good_delta,corrections.c.scrap_delta).where(corrections.c.report_id==row_id)).all()
        if report['good_quantity']+sum((x[0] for x in original_fixes),Decimal(0))+b.good_delta<0 or report['scrap_quantity']+sum((x[1] for x in original_fixes),Decimal(0))+b.scrap_delta<0:raise HTTPException(409,'Đính chính làm âm số liệu báo cáo gốc')
        operations=c.execute(sa.select(op).where(op.c.production_order_id==order['id']).order_by(op.c.sequence_no)).mappings().all()
        index=next(i for i,o in enumerate(operations) if o['id']==operation['id'])
        capacity=operation_capacity(c,p,order,operations,index)
        good,scrap=operation_totals(c,p.organization_id,operation['id'])
        good+=b.good_delta;scrap+=b.scrap_delta
        if good<0 or scrap<0 or good+scrap>capacity:raise HTTPException(409,'Sản lượng sau đính chính vượt đầu vào công đoạn')
        rid=str(__import__('uuid').uuid4())
        c.execute(corrections.insert().values(id=rid,organization_id=p.organization_id,report_id=row_id,good_delta=b.good_delta,scrap_delta=b.scrap_delta,reason=b.reason,actor_user_id=p.user_id,created_at=utcnow()))
        done=good+scrap==capacity
        c.execute(op.update().where(op.c.id==operation['id']).values(status='completed' if done else 'in_progress',actual_end_at=utcnow() if done else None,updated_at=utcnow()))
        refresh_following_operations(c,p,operations)
        refresh_order_totals(c,p,order['id'],operations)
        audit(c,p,'correct_production_report','production_report_corrections',rid,{'report_id':row_id,'good_delta':str(b.good_delta),'scrap_delta':str(b.scrap_delta),'reason':b.reason})
        return {'id':rid,'report_id':row_id,'operation_good_quantity':str(good),'operation_scrap_quantity':str(scrap)}
    return perform(request,'production.write',b,run)

@router.post('/production-orders/{row_id}/complete')
def complete(row_id:str,b:Ship,request:Request):
    def run(c,p,key):
        order=get(c,'production_orders',row_id,p,'production.write');ops=md.tables['production_order_operations']
        if order['status']!='in_progress' or order['good_quantity']+order['scrap_quantity']!=order['released_quantity']:raise HTTPException(409,'Lệnh chưa đủ báo cáo sản lượng cuối cùng')
        if c.execute(sa.select(ops.c.id).where(ops.c.production_order_id==row_id,ops.c.status!='completed')).first():raise HTTPException(409,'Còn công đoạn chưa hoàn thành')
        consumed=material_cost(c,p.organization_id,row_id)
        output_unit_cost=money(Decimal(consumed)/order['good_quantity']) if order['good_quantity'] else 0
        result=None
        if order['good_quantity']>0:result=receive_unit(c,p,order['product_id'],str(b.warehouse_id),order['good_quantity'],output_unit_cost,key,'finished',reference_type='production_order',reference_id=row_id,kind='production_output')
        c.execute(md.tables['production_orders'].update().where(md.tables['production_orders'].c.id==row_id).values(status='completed',actual_end_at=utcnow(),updated_at=utcnow()))
        loss=consumed if not order['good_quantity'] else 0
        variance=consumed-loss-money(order['good_quantity']*output_unit_cost)
        audit(c,p,'complete','production_orders',row_id,{'material_cost_vnd':consumed,'output_unit_cost_vnd':output_unit_cost,'rounding_variance_vnd':variance,'scrap_material_cost_vnd':loss,'valuation_basis':'actual_material_consumption'})
        return {'id':row_id,'status':'completed','output':result,'scrap_quantity':str(order['scrap_quantity']),'material_cost_vnd':consumed,'rounding_variance_vnd':variance,'scrap_material_cost_vnd':loss,'unmodeled_costs':['labor','overhead']}
    return perform(request,'production.write',b,run)

@router.post('/tasks/{row_id}/updates')
def task_update(row_id:str,b:TaskUpdate,request:Request):
    def run(c,p,key):
        task=get(c,'tasks',row_id,p,'tasks.update')
        allowed={'open':{'in_progress','blocked','cancelled'},'in_progress':{'in_progress','blocked','completed','cancelled'},'blocked':{'in_progress','cancelled'}}
        if b.status not in allowed.get(task['status'],set()):raise HTTPException(409,'Không thể chuyển trạng thái công việc')
        if b.status=='completed' and b.progress_percent!=100:raise HTTPException(422,'Hoàn thành cần tiến độ 100%')
        if b.status=='cancelled' and 'ADMIN' not in p.roles and task['created_by']!=p.user_id:raise HTTPException(403,'Chỉ người giao việc được hủy')
        c.execute(md.tables['task_updates'].insert().values(organization_id=p.organization_id,task_id=row_id,employee_id=p.employee_id,update_type='status_change',content=b.content,progress_percent=b.progress_percent))
        c.execute(md.tables['tasks'].update().where(md.tables['tasks'].c.id==row_id).values(status=b.status,completed_at=utcnow() if b.status=='completed' else None,updated_at=utcnow()))
        audit(c,p,'task_'+b.status,'tasks',row_id)
        return {'id':row_id,'status':b.status,'progress_percent':b.progress_percent}
    return perform(request,'tasks.update',b,run)
