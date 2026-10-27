from concurrent.futures import ThreadPoolExecutor
import uuid
import sqlalchemy as sa
from backend.app.models import metadata as md
from .test_business import post
from .test_inventory import action

def invoice(c,h,customer,code='INV',amount=1000):
    inv=post(c,h,'customer-invoices',{'invoice_no':code,'customer_id':customer['id'],'invoice_date':'2026-10-25','due_date':'2026-11-25','lines':[{'line_no':1,'description':'Thảm bê tông','quantity':'1','uom':'m2','unit_price':amount}]})
    r=action(c,h,'customer-invoices/'+inv['id']+'/issue');assert r.status_code==200,r.text
    return inv

def test_customer_partial_topup_events_and_concurrent_allocation(erp):
    c,login,a,b=erp;h=login();customer=post(c,h,'customers',{'customer_code':'KH1','name':'One'})
    inv=invoice(c,h,customer)
    receipt=post(c,h,'customer-receipts',{'receipt_code':'PT1','customer_id':customer['id'],'amount':1000,'payment_method':'bank_transfer'})
    body={'invoice_id':inv['id'],'amount':400}
    assert action(c,h,'customer-receipts/'+receipt['id']+'/allocations',body).status_code==409
    assert action(c,h,'customer-receipts/'+receipt['id']+'/verify').status_code==200
    key=str(uuid.uuid4());r=action(c,h,'customer-receipts/'+receipt['id']+'/allocations',body,key)
    assert r.status_code==200,r.text
    assert r.json()['invoice_remaining']==600
    assert action(c,h,'customer-receipts/'+receipt['id']+'/allocations',body,key).json()==r.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:action(c,h,'customer-receipts/'+receipt['id']+'/allocations',{'invoice_id':inv['id'],'amount':400}),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    r=action(c,h,'customer-receipts/'+receipt['id']+'/allocations',{'invoice_id':inv['id'],'amount':200});assert r.status_code==200,r.text
    assert r.json()['invoice_remaining']==0
    inv_now=c.get('/api/v1/customer-invoices/'+inv['id'],headers=h).json();assert inv_now['status']=='paid'
    customer_now=c.get('/api/v1/customers/'+customer['id'],headers=h).json();assert customer_now['current_debt_amount']==0
    with c.app.state.engine.begin() as conn:
        assert conn.exec_driver_sql('SELECT SUM(amount),COUNT(*) FROM payment_allocation_events').one()==(1000,3)
        assert conn.exec_driver_sql('SELECT amount FROM customer_payment_allocations').scalar_one()==1000
    assert c.patch('/api/v1/customer-invoices/'+inv['id'],headers=h,json={'invoice_date':'2020-01-01'}).status_code==409

def test_cross_customer_or_tenant_allocation_and_supplier_payables(erp):
    c,login,a,b=erp;h=login();one=post(c,h,'customers',{'customer_code':'ONE','name':'One'});two=post(c,h,'customers',{'customer_code':'TWO','name':'Two'})
    inv=invoice(c,h,one)
    receipt=post(c,h,'customer-receipts',{'receipt_code':'PT','customer_id':two['id'],'amount':1000,'payment_method':'cash'})
    assert action(c,h,'customer-receipts/'+receipt['id']+'/verify').status_code==200
    assert action(c,h,'customer-receipts/'+receipt['id']+'/allocations',{'invoice_id':inv['id'],'amount':100}).status_code==422
    assert action(c,login('admin_b'),'customer-receipts/'+receipt['id']+'/allocations',{'invoice_id':inv['id'],'amount':100}).status_code==404
    supplier=post(c,h,'suppliers',{'supplier_code':'SUP','name':'Supplier'})
    bill=post(c,h,'supplier-bills',{'supplier_id':supplier['id'],'bill_no':'BILL','bill_date':'2026-10-25','due_date':'2026-11-10','subtotal_amount':1000,'tax_amount':100})
    assert bill['total_amount']==1100
    assert action(c,h,'supplier-bills/'+bill['id']+'/post').status_code==200
    payment=post(c,h,'supplier-payments',{'supplier_id':supplier['id'],'payment_code':'PC1','amount':1100,'payment_method':'cash'})
    assert action(c,h,'supplier-payments/'+payment['id']+'/verify').status_code==200
    r=action(c,h,'supplier-payments/'+payment['id']+'/allocations',{'bill_id':bill['id'],'amount':1100});assert r.status_code==200,r.text
    assert r.json()['invoice_remaining']==0
    assert c.get('/api/v1/supplier-bills/'+bill['id'],headers=h).json()['status']=='paid'
