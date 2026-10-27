import uuid
from .conftest import add_user

def post(c,h,path,data,status=201):
    r=c.post('/api/v1/'+path,headers=h,json=data)
    assert r.status_code==status,r.text
    return r.json()

def product(c,h,sku='FLEX'):
    return post(c,h,'products',{'sku':sku,'name':'Thảm FLEX 3D','base_uom':'m2','product_type':'finished_good','standard_cost':15000,'is_manufactured':True})

def test_sales_exact_money_ownership_state_and_tenant(erp):
    c,login,a,b=erp;h=login();p=product(c,h)
    uid,eid=add_user(c,a['organization_id'],'ctv','CTV');ch=login('ctv')
    cust=post(c,ch,'customers',{'customer_code':'KH1','name':'Khách hàng một'})
    assert cust['owner_employee_id']==eid and eid!=uid
    order=post(c,ch,'sales-orders',{'order_code':'SO1','customer_id':cust['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':'1.234567','uom':'m2','unit_price':190001,'discount_amount':1,'tax_rate':1000}]})
    assert order['subtotal_amount']==234569 and order['tax_amount']==23457 and order['total_amount']==258025
    other_uid,other_eid=add_user(c,a['organization_id'],'ctv2','CTV');other=login('ctv2')
    assert c.get('/api/v1/sales-orders/'+order['id'],headers=other).status_code==404
    assert c.patch('/api/v1/customers/'+cust['id'],headers=ch,json={'owner_employee_id':other_eid}).status_code==403
    assert c.get('/api/v1/customers',headers=other).json()['total']==0
    assert c.get('/api/v1/customers/'+cust['id'],headers=login('admin_b')).status_code==404
    key={'Idempotency-Key':str(uuid.uuid4())}
    assert c.post('/api/v1/sales-orders/'+order['id']+'/confirm',headers={**ch,**key},json={}).status_code==403
    r=c.post('/api/v1/sales-orders/'+order['id']+'/confirm',headers={**h,**key},json={});assert r.status_code==200,r.text
    assert c.post('/api/v1/sales-orders/'+order['id']+'/confirm',headers={**h,**key},json={}).json()==r.json()
    assert c.patch('/api/v1/sales-orders/'+order['id'],headers=h,json={'notes':'Cannot edit posted'}).status_code==409
    assert c.post('/api/v1/sales-orders/'+order['id']+'/confirm',headers={**h,'Idempotency-Key':str(uuid.uuid4())},json={}).status_code==409

def test_purchase_rejects_cross_tenant_and_payload_bypass(erp):
    c,login,a,b=erp;h=login();p=product(c,h);supplier=post(c,h,'suppliers',{'supplier_code':'SUP1','name':'Nhà cung cấp'})
    body={'po_code':'PO1','supplier_id':supplier['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':'2.5','uom':'m2','unit_price':1001,'tax_amount':250}]}
    po=post(c,h,'purchase-orders',body)
    assert po['subtotal_amount']==2503 and po['total_amount']==2753
    assert c.post('/api/v1/purchase-orders',headers=login('admin_b'),json={**body,'po_code':'PO2'}).status_code==404
    assert c.post('/api/v1/purchase-orders',headers=h,json={**body,'status':'received'}).status_code==422
    assert c.post('/api/v1/purchase-orders',headers=h,json={**body,'total_amount':1}).status_code==422
    assert c.post('/api/v1/purchase-orders',headers=h,json=body).status_code==409
    assert c.get('/api/v1/suppliers?sort=name%20DESC;DROP%20TABLE%20customers',headers=h).status_code==422
    assert c.get('/api/v1/products?page_size=999999',headers=h).status_code==422

def test_draft_replace_lines_recalculates_and_rolls_back_on_error(erp):
    c,login,a,b=erp;h=login();p=product(c,h);cust=post(c,h,'customers',{'customer_code':'KH','name':'Customer'})
    o=post(c,h,'sales-orders',{'order_code':'SO','customer_id':cust['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':'2','uom':'m2','unit_price':5000}]})
    r=c.patch('/api/v1/sales-orders/'+o['id'],headers=h,json={'lines':[{'line_no':1,'product_id':p['id'],'quantity':'3','uom':'m2','unit_price':5000}]})
    assert r.status_code==200,r.text
    assert r.json()['total_amount']==15000
    r=c.patch('/api/v1/sales-orders/'+o['id'],headers=h,json={'lines':[]})
    assert r.status_code==422
    assert c.get('/api/v1/sales-orders/'+o['id'],headers=h).json()['total_amount']==15000
