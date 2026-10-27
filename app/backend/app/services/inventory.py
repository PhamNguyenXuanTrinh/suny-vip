from decimal import Decimal
from datetime import datetime
from uuid import UUID
import uuid,hashlib
import sqlalchemy as sa
from pydantic import BaseModel,ConfigDict,Field
from fastapi import APIRouter,Request,HTTPException
from backend.app.models import metadata as md
from backend.app.models.base import utcnow
from backend.app.core.tenancy import scope
from backend.app.services.data import get,foreign_keys,money
from backend.app.services.auth import audit
from backend.app.services.workflows import perform,Empty,transition

from backend.app.schemas.common import PostingRouter
router=PostingRouter(prefix='/api/v1',tags=['Inventory and fulfillment'])
class Input(BaseModel):model_config=ConfigDict(extra='forbid')
class Receipt(Input):
    product_id:UUID
    warehouse_id:UUID
    quantity:Decimal=Field(gt=0,max_digits=18,decimal_places=6)
    unit_cost:int=Field(strict=True,ge=0,le=10**15)
    roll_code:str|None=Field(default=None,min_length=1,max_length=100)
    lot_id:UUID|None=None
    location_id:UUID|None=None
class Adjustment(Input):
    inventory_unit_id:UUID
    quantity_delta:Decimal=Field(max_digits=18,decimal_places=6)
    reason:str=Field(min_length=8,max_length=2000)
    reversal_of:UUID|None=None
class Issue(Input):
    inventory_unit_id:UUID
    quantity:Decimal=Field(gt=0,max_digits=18,decimal_places=6)
    reason:str=Field(min_length=8,max_length=2000)
class POLine(Input):
    purchase_order_line_id:UUID
    warehouse_id:UUID
    quantity:Decimal=Field(gt=0,max_digits=18,decimal_places=6)
    roll_code:str|None=Field(default=None,min_length=1,max_length=100)
    lot_id:UUID|None=None
    location_id:UUID|None=None
class POReceipt(Input):lines:list[POLine]=Field(min_length=1,max_length=200)
class Ship(Input):warehouse_id:UUID

def movement(c,p,unit_id,delta,kind,key,suffix,reference_type,reference_id,permission='inventory.write'):
    unit=get(c,'inventory_units',unit_id,p,permission)
    if delta==0:raise HTTPException(422,'Bút toán kho phải có số lượng khác 0')
    if delta<0 and unit['status']!='available':raise HTTPException(409,'Cuộn không ở trạng thái sẵn sàng để xuất')
    remaining=unit['remaining_quantity']+delta
    if remaining<0:raise HTTPException(409,'Số lượng xuất vượt tồn khả dụng')
    code='MV-'+uuid.uuid4().hex;rid=str(uuid.uuid4())
    c.execute(md.tables['inventory_movements'].insert().values(id=rid,organization_id=p.organization_id,movement_code=code,movement_type=kind,product_id=unit['product_id'],inventory_unit_id=unit_id,lot_id=unit['lot_id'],warehouse_id=unit['warehouse_id'],location_id=unit['location_id'],quantity_delta=delta,unit_cost=unit['unit_cost'],total_value=money(abs(delta)*unit['unit_cost']),reference_type=reference_type,reference_id=reference_id,idempotency_key=hashlib.sha256((key+':'+suffix).encode()).hexdigest(),actor_user_id=p.user_id))
    c.execute(md.tables['inventory_units'].update().where(md.tables['inventory_units'].c.id==unit_id).values(remaining_quantity=remaining,status='consumed' if remaining==0 else 'available',updated_at=utcnow()))
    audit(c,p,'inventory_'+kind,'inventory_movements',rid,{'quantity_delta':str(delta),'reference_type':reference_type,'reference_id':reference_id})
    return {'movement_id':rid,'inventory_unit_id':unit_id,'remaining_quantity':str(remaining)}

def receive_unit(c,p,product_id,warehouse_id,quantity,unit_cost,key,suffix,roll_code=None,lot_id=None,location_id=None,reference_type='manual_receipt',reference_id=None,kind='receipt'):
    product=get(c,'products',product_id,p,'inventory.write')
    get(c,'warehouses',warehouse_id,p,'inventory.write')
    row={'product_id':product_id,'warehouse_id':warehouse_id,'lot_id':lot_id,'location_id':location_id}
    foreign_keys(c,'inventory_units',row,p,'inventory.write')
    rid=str(uuid.uuid4())
    c.execute(md.tables['inventory_units'].insert().values(id=rid,organization_id=p.organization_id,product_id=product_id,warehouse_id=warehouse_id,lot_id=lot_id,location_id=location_id,roll_code=roll_code or 'ROLL-'+uuid.uuid4().hex,initial_quantity=quantity,remaining_quantity=0,uom=product['base_uom'],unit_cost=unit_cost,status='available'))
    return movement(c,p,rid,quantity,kind,key,suffix,reference_type,reference_id)

@router.post('/inventory-movements/receipt')
def receipt(b:Receipt,request:Request):
    def run(c,p,key):
        return receive_unit(c,p,str(b.product_id),str(b.warehouse_id),b.quantity,b.unit_cost,key,'receipt',b.roll_code,str(b.lot_id) if b.lot_id else None,str(b.location_id) if b.location_id else None)
    return perform(request,'inventory.write',b,run)

@router.post('/inventory-movements/issue')
def issue(b:Issue,request:Request):
    def run(c,p,key):
        result=movement(c,p,str(b.inventory_unit_id),-b.quantity,'issue',key,'issue','manual_issue',None)
        audit(c,p,'manual_issue_reason','inventory_movements',result['movement_id'],{'reason':b.reason})
        return result
    return perform(request,'inventory.write',b,run)

@router.post('/inventory-movements/adjustment')
def adjustment(b:Adjustment,request:Request):
    def run(c,p,key):
        unit=get(c,'inventory_units',str(b.inventory_unit_id),p,'inventory.adjust')
        if b.reversal_of:
            original=get(c,'inventory_movements',str(b.reversal_of),p,'inventory.adjust')
            if original['reference_type'] not in ('manual_receipt','manual_issue','inventory_adjustment'):raise HTTPException(409,'Giao dịch gắn chứng từ nguồn cần được đối soát theo chứng từ, không đảo riêng bút toán kho')
            if original['inventory_unit_id']!=unit['id'] or b.quantity_delta!=-original['quantity_delta']:raise HTTPException(422,'Bút toán đảo không khớp bút toán gốc')
            m=md.tables['inventory_movements']
            if c.execute(sa.select(m.c.id).where(m.c.organization_id==p.organization_id,m.c.reference_type=='inventory_reversal',m.c.reference_id==str(b.reversal_of))).first():raise HTTPException(409,'Bút toán gốc đã được đảo')
        result=movement(c,p,unit['id'],b.quantity_delta,'reversal' if b.reversal_of else 'adjustment',key,'adjust','inventory_reversal' if b.reversal_of else 'inventory_adjustment',str(b.reversal_of) if b.reversal_of else None,'inventory.adjust')
        audit(c,p,'adjustment_reason','inventory_movements',result['movement_id'],{'reason':b.reason})
        return result
    return perform(request,'inventory.adjust',b,run)

@router.post('/purchase-orders/{row_id}/receive')
def receive_po(row_id:str,b:POReceipt,request:Request):
    def run(c,p,key):
        t=md.tables['purchase_orders'];lines=md.tables['purchase_order_lines']
        po=c.execute(sa.select(t).where(t.c.id==row_id,t.c.organization_id==p.organization_id)).mappings().first()
        if not po:raise HTTPException(404,'Không tìm thấy đơn mua')
        if po['status'] not in ('approved','partially_received'):raise HTTPException(409,'Đơn mua chưa được duyệt hoặc đã đóng')
        seen=set();results=[]
        for index,line in enumerate(b.lines):
            lid=str(line.purchase_order_line_id)
            if lid in seen:raise HTTPException(422,'Dòng nhận hàng bị trùng')
            seen.add(lid)
            source=c.execute(sa.select(lines).where(lines.c.id==lid,lines.c.purchase_order_id==row_id,lines.c.organization_id==p.organization_id)).mappings().first()
            if not source:raise HTTPException(404,'Dòng hàng không thuộc đơn mua')
            if line.quantity>source['quantity']-source['received_quantity']:raise HTTPException(409,'Nhận vượt số lượng còn lại của đơn mua')
            results.append(receive_unit(c,p,source['product_id'],str(line.warehouse_id),line.quantity,source['unit_price'],key,str(index),line.roll_code,str(line.lot_id) if line.lot_id else None,str(line.location_id) if line.location_id else None,'purchase_order_line',lid))
            c.execute(lines.update().where(lines.c.id==lid).values(received_quantity=source['received_quantity']+line.quantity))
        remaining=c.execute(sa.select(lines.c.id).where(lines.c.purchase_order_id==row_id,lines.c.received_quantity<lines.c.quantity)).first()
        state='partially_received' if remaining else 'received'
        c.execute(t.update().where(t.c.id==row_id).values(status=state,updated_at=utcnow()))
        audit(c,p,'receive','purchase_orders',row_id)
        return {'id':row_id,'status':state,'receipts':results}
    return perform(request,'purchasing.receive',b,run)

@router.post('/shipments/{row_id}/ship')
def ship(row_id:str,b:Ship,request:Request):
    def run(c,p,key):
        shipment=get(c,'shipments',row_id,p,'shipments.ship');get(c,'warehouses',str(b.warehouse_id),p,'shipments.ship')
        if shipment['status'] not in ('draft','ready'):raise HTTPException(409,'Phiếu giao không ở trạng thái cho phép xuất')
        sl=md.tables['shipment_lines'];shipments=md.tables['shipments'];so=md.tables['sales_orders'];sol=md.tables['sales_order_lines'];units=md.tables['inventory_units']
        if shipment['sales_order_id']:
            order=get(c,'sales_orders',shipment['sales_order_id'],p,'shipments.ship')
            if order['status'] not in ('confirmed','in_progress'):raise HTTPException(409,'Đơn bán chưa xác nhận hoặc đã đóng')
        lines=c.execute(sa.select(sl).where(sl.c.shipment_id==row_id,sl.c.organization_id==p.organization_id)).mappings().all()
        if not lines:raise HTTPException(409,'Phiếu giao chưa có dòng hàng')
        results=[]
        for line in lines:
            if shipment['sales_order_id'] or line['sales_order_line_id']:
                source=c.execute(sa.select(sol).where(sol.c.id==line['sales_order_line_id'],sol.c.product_id==line['product_id'])).mappings().first()
                if not source:raise HTTPException(422,'Dòng giao không khớp dòng đơn bán')
                source_order=get(c,'sales_orders',source['order_id'],p,'shipments.ship')
                if source_order['customer_id']!=shipment['customer_id'] or shipment['sales_order_id'] not in (None,source_order['id']):raise HTTPException(422,'Dòng giao không khớp khách hàng hoặc đơn bán')
                if source_order['status'] not in ('confirmed','in_progress'):raise HTTPException(409,'Đơn bán nguồn chưa xác nhận hoặc đã đóng')
                already=sum((r[0] for r in c.execute(sa.select(sl.c.quantity).join(shipments,shipments.c.id==sl.c.shipment_id).where(sl.c.sales_order_line_id==source['id'],shipments.c.status.in_(['shipped','delivered'])))),Decimal(0))
                pending=sum((x['quantity'] for x in lines if x['sales_order_line_id']==source['id']),Decimal(0))
                if already+pending>source['quantity']:raise HTTPException(409,'Giao vượt số lượng đã đặt')
            rows=c.execute(sa.select(units).where(units.c.organization_id==p.organization_id,units.c.warehouse_id==str(b.warehouse_id),units.c.product_id==line['product_id'],units.c.status=='available',units.c.remaining_quantity>0).order_by(units.c.received_at,units.c.id)).mappings().all()
            need=line['quantity']
            for unit in rows:
                take=min(need,unit['remaining_quantity'])
                if take>0:results.append(movement(c,p,unit['id'],-take,'issue',key,line['id']+unit['id'],'shipment_line',line['id'],'shipments.ship'));need-=take
                if need==0:break
            if need>0:raise HTTPException(409,'Không đủ tồn để xuất giao')
        c.execute(shipments.update().where(shipments.c.id==row_id).values(status='shipped',shipped_at=utcnow()))
        if shipment['sales_order_id']:c.execute(so.update().where(so.c.id==shipment['sales_order_id']).values(status='in_progress',updated_at=utcnow()))
        audit(c,p,'ship','shipments',row_id)
        return {'id':row_id,'status':'shipped','movements':results}
    return perform(request,'shipments.ship',b,run)

@router.post('/shipments/{row_id}/deliver')
def deliver(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        result=transition(c,p,'shipments',row_id,'shipments.deliver',{'shipped'},'delivered')
        c.execute(md.tables['shipments'].update().where(md.tables['shipments'].c.id==row_id).values(delivered_at=utcnow()))
        sl=md.tables['shipment_lines'];ol=md.tables['sales_order_lines'];orders=md.tables['sales_orders'];ships=md.tables['shipments']
        source_orders=set(c.execute(sa.select(ol.c.order_id).join(sl,sl.c.sales_order_line_id==ol.c.id).where(sl.c.shipment_id==row_id)).scalars())
        for order_id in source_orders:
            complete=True
            for source in c.execute(sa.select(ol).where(ol.c.order_id==order_id)).mappings():
                delivered=sum((r[0] for r in c.execute(sa.select(sl.c.quantity).join(ships,ships.c.id==sl.c.shipment_id).where(sl.c.sales_order_line_id==source['id'],ships.c.status=='delivered'))),Decimal(0))
                if delivered<source['quantity']:complete=False;break
            c.execute(orders.update().where(orders.c.id==order_id).values(status='completed' if complete else 'in_progress',updated_at=utcnow()))
        return result
    return perform(request,'shipments.deliver',b,run)

@router.post('/stock-transfers/{row_id}/ship')
def transfer_ship(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        transfer=get(c,'stock_transfers',row_id,p,'inventory.write');t=md.tables['stock_transfers'];lines=md.tables['stock_transfer_lines']
        if transfer['status'] not in ('draft','requested'):raise HTTPException(409,'Phiếu điều chuyển không cho phép xuất')
        rows=c.execute(sa.select(lines).where(lines.c.transfer_id==row_id)).mappings().all()
        if not rows:raise HTTPException(409,'Phiếu điều chuyển chưa có dòng hàng')
        seen=set()
        for line in rows:
            if not line['inventory_unit_id']:raise HTTPException(422,'Điều chuyển cần xác định cuộn/vật tư')
            if line['inventory_unit_id'] in seen:raise HTTPException(422,'Mỗi cuộn chỉ được xuất hiện một lần trên phiếu điều chuyển')
            seen.add(line['inventory_unit_id'])
            unit=get(c,'inventory_units',line['inventory_unit_id'],p,'inventory.write')
            if unit['warehouse_id']!=transfer['from_warehouse_id'] or unit['product_id']!=line['product_id'] or unit['uom']!=line['uom'] or line['lot_id'] not in (None,unit['lot_id']):raise HTTPException(422,'Cuộn điều chuyển không khớp kho, sản phẩm hoặc lô')
            movement(c,p,unit['id'],-line['quantity'],'transfer_out',key,line['id'],'stock_transfer_line',line['id'])
            if line['quantity']==unit['remaining_quantity']:
                c.execute(md.tables['inventory_units'].update().where(md.tables['inventory_units'].c.id==unit['id']).values(status='in_transit'))
        c.execute(t.update().where(t.c.id==row_id).values(status='shipped',shipped_at=utcnow(),updated_at=utcnow()))
        audit(c,p,'ship','stock_transfers',row_id)
        return {'id':row_id,'status':'shipped','in_transit':True}
    return perform(request,'inventory.write',b,run)

@router.post('/stock-transfers/{row_id}/receive')
def transfer_receive(row_id:str,b:Empty,request:Request):
    def run(c,p,key):
        transfer=get(c,'stock_transfers',row_id,p,'inventory.write');t=md.tables['stock_transfers'];lines=md.tables['stock_transfer_lines']
        if transfer['status']!='shipped':raise HTTPException(409,'Điều chuyển phải được xuất trước khi nhận')
        rows=c.execute(sa.select(lines).where(lines.c.transfer_id==row_id)).mappings().all();results=[]
        for line in rows:
            unit=get(c,'inventory_units',line['inventory_unit_id'],p,'inventory.write')
            if unit['status']=='in_transit':
                c.execute(md.tables['inventory_units'].update().where(md.tables['inventory_units'].c.id==unit['id']).values(warehouse_id=transfer['to_warehouse_id'],location_id=None,status='available'))
                results.append(movement(c,p,unit['id'],line['quantity'],'transfer_in',key,line['id'],'stock_transfer_line',line['id']))
            else:
                results.append(receive_unit(c,p,line['product_id'],transfer['to_warehouse_id'],line['quantity'],unit['unit_cost'],key,line['id'],'TR-'+line['id'],unit['lot_id'],None,'stock_transfer_line',line['id'],'transfer_in'))
        c.execute(t.update().where(t.c.id==row_id).values(status='received',received_at=utcnow(),updated_at=utcnow()))
        audit(c,p,'receive','stock_transfers',row_id)
        return {'id':row_id,'status':'received','receipts':results}
    return perform(request,'inventory.write',b,run)
