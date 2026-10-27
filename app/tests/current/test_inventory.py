from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import uuid
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
import pytest
from backend.app.models import metadata as md
from .test_business import post,product

def action(c,h,path,data=None,key=None):
    return c.post('/api/v1/'+path,headers={**h,'Idempotency-Key':key or str(uuid.uuid4())},json=data or {})

def warehouse(c,h,code='W'):
    site=post(c,h,'sites',{'code':code,'name':'Factory'})
    return post(c,h,'warehouses',{'site_id':site['id'],'code':code,'name':'Warehouse '+code})

def receipt(c,h,p,w,quantity='10',key=None):
    r=action(c,h,'inventory-movements/receipt',{'product_id':p['id'],'warehouse_id':w['id'],'quantity':quantity,'unit_cost':10001},key)
    assert r.status_code==200,r.text
    return r.json()

def test_inventory_idempotency_immutability_and_concurrent_oversell(erp):
    c,login,a,b=erp;h=login();p=product(c,h);w=warehouse(c,h)
    key=str(uuid.uuid4());unit=receipt(c,h,p,w,key=key)
    assert receipt(c,h,p,w,key=key)==unit
    assert action(c,h,'inventory-movements/receipt',{'product_id':p['id'],'warehouse_id':w['id'],'quantity':'11','unit_cost':10001},key).status_code==409
    data={'inventory_unit_id':unit['inventory_unit_id'],'quantity':'7','reason':'Xuất cho sản xuất'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:action(c,h,'inventory-movements/issue',data),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    actual=c.get('/api/v1/inventory-units/'+unit['inventory_unit_id'],headers=h).json()
    assert Decimal(actual['remaining_quantity'])==3
    movements=c.get('/api/v1/inventory-movements',headers=h).json()['items']
    assert len(movements)==2 and sum(Decimal(m['quantity_delta']) for m in movements)==3
    assert all(m['total_value']>0 for m in movements)
    for sql in ('UPDATE inventory_movements SET total_value=1','DELETE FROM inventory_movements'):
        with pytest.raises(IntegrityError),c.app.state.engine.begin() as conn:conn.exec_driver_sql(sql)
    assert c.get('/api/v1/inventory-units/'+unit['inventory_unit_id'],headers=login('admin_b')).status_code==404

def test_po_partial_receipt_and_transfer_atomicity(erp):
    c,login,a,b=erp;h=login();p=product(c,h);w=warehouse(c,h);w2=warehouse(c,h,'W2')
    sup=post(c,h,'suppliers',{'supplier_code':'SUP','name':'Supplier'})
    po=post(c,h,'purchase-orders',{'po_code':'PO','supplier_id':sup['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':'10.5','uom':'m2','unit_price':1000}]})
    lid=c.get('/api/v1/purchase-orders/'+po['id'],headers=h).json()['lines'][0]['id']
    body={'lines':[{'purchase_order_line_id':lid,'warehouse_id':w['id'],'quantity':'4.5'}]}
    assert action(c,h,'purchase-orders/'+po['id']+'/receive',body).status_code==409
    assert action(c,h,'purchase-orders/'+po['id']+'/approve').status_code==200
    r=action(c,h,'purchase-orders/'+po['id']+'/receive',body);assert r.status_code==200,r.text
    assert r.json()['status']=='partially_received';unit=r.json()['receipts'][0]['inventory_unit_id']
    transfer=post(c,h,'stock-transfers',{'transfer_code':'TR1','from_warehouse_id':w['id'],'to_warehouse_id':w2['id'],'lines':[{'product_id':p['id'],'inventory_unit_id':unit,'quantity':'2.5','uom':'m2'}]})
    assert action(c,h,'stock-transfers/'+transfer['id']+'/receive').status_code==409
    assert action(c,h,'stock-transfers/'+transfer['id']+'/ship').status_code==200
    assert Decimal(c.get('/api/v1/inventory-units/'+unit,headers=h).json()['remaining_quantity'])==2
    r=action(c,h,'stock-transfers/'+transfer['id']+'/receive');assert r.status_code==200,r.text
    target=c.get('/api/v1/inventory-units/'+r.json()['receipts'][0]['inventory_unit_id'],headers=h).json()
    assert target['warehouse_id']==w2['id'] and Decimal(target['remaining_quantity'])==Decimal('2.5')
    assert action(c,h,'purchase-orders/'+po['id']+'/receive',{'lines':[{'purchase_order_line_id':lid,'warehouse_id':w['id'],'quantity':'7'}]}).status_code==409
    r=action(c,h,'purchase-orders/'+po['id']+'/receive',{'lines':[{'purchase_order_line_id':lid,'warehouse_id':w['id'],'quantity':'6'}]})
    assert r.status_code==200 and r.json()['status']=='received'

def test_shipments_require_confirmed_orders_and_cannot_overship(erp):
    c,login,a,b=erp;h=login();p=product(c,h);w=warehouse(c,h);receipt(c,h,p,w)
    customer=post(c,h,'customers',{'customer_code':'KH','name':'Customer'})
    order=post(c,h,'sales-orders',{'order_code':'SO','customer_id':customer['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':'3','uom':'m2','unit_price':2000}]})
    lid=c.get('/api/v1/sales-orders/'+order['id'],headers=h).json()['lines'][0]['id']
    shipment=post(c,h,'shipments',{'shipment_code':'SH1','customer_id':customer['id'],'sales_order_id':order['id'],'lines':[{'sales_order_line_id':lid,'product_id':p['id'],'quantity':'3','uom':'m2'}]})
    assert action(c,h,'shipments/'+shipment['id']+'/ship',{'warehouse_id':w['id']}).status_code==409
    assert action(c,h,'sales-orders/'+order['id']+'/confirm').status_code==200
    r=action(c,h,'shipments/'+shipment['id']+'/ship',{'warehouse_id':w['id']});assert r.status_code==200,r.text
    assert action(c,h,'shipments/'+shipment['id']+'/deliver').status_code==200
    too_many=post(c,h,'shipments',{'shipment_code':'SH2','customer_id':customer['id'],'sales_order_id':order['id'],'lines':[{'sales_order_line_id':lid,'product_id':p['id'],'quantity':'1','uom':'m2'}]})
    assert action(c,h,'shipments/'+too_many['id']+'/ship',{'warehouse_id':w['id']}).status_code==409
