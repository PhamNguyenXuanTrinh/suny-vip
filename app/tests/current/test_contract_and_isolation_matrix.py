import tempfile
from pathlib import Path
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from backend.app.models import metadata as md
from backend.app.database import make_engine
from backend.scripts.migrate_db import migrate
from backend.app.services.data import NAMES
from .test_business import post,product
from .test_inventory import action,warehouse,receipt
from .test_finance import invoice

def test_migrations_and_sqlalchemy_schema_have_no_drift(tmp_path):
    p=tmp_path/'schema.sqlite3';migrate(p);engine=make_engine('sqlite:///'+str(p))
    with engine.begin() as c:
        assert compare_metadata(MigrationContext.configure(c),md)==[]
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all()==[]

def test_openapi_has_real_response_contracts_posting_headers_and_errors(erp):
    c,login,a,b=erp;s=c.get('/api/openapi.json').json()
    response=s['paths']['/api/v1/customers/{row_id}']['get']['responses']['200']['content']['application/json']['schema']
    assert response['$ref'].endswith('customersOutput')
    fields=s['components']['schemas']['customersOutput']['properties']
    assert fields['current_debt_amount']['type']=='integer'
    movement=s['paths']['/api/v1/inventory-movements/receipt']['post']
    assert any(h['name']=='Idempotency-Key' and h['required'] for h in movement['parameters'])
    assert movement['responses']['200']['content']['application/json']['schema']['$ref'].endswith('PostingResult')
    assert 'ErrorEnvelope' in s['components']['schemas']
    assert s['components']['securitySchemes']['BearerAuth']['scheme']=='bearer'
    assert s['paths']['/api/v1/customers']['get']['security']==[{'BearerAuth':[]}]
    assert '/api/_docs/swagger-ui-bundle.js' in c.get('/api/docs').text
    assert 'password_hash' not in str(s['components']['schemas']['app_usersOutput']) if 'app_usersOutput' in s['components']['schemas'] else True

def test_lists_details_and_foreign_references_do_not_cross_tenants(erp):
    c,login,a,b=erp;ha=login();hb=login('admin_b');product_b=product(c,hb);w=warehouse(c,hb);u=receipt(c,hb,product_b,w,'20')
    customer=post(c,hb,'customers',{'customer_code':'B-CUSTOMER','name':'Private tenant B'})
    post(c,hb,'customer-contacts',{'customer_id':customer['id'],'full_name':'Contact B'})
    order=post(c,hb,'sales-orders',{'order_code':'B-SO','customer_id':customer['id'],'lines':[{'line_no':1,'product_id':product_b['id'],'quantity':'2','uom':'m2','unit_price':10000}]})
    assert action(c,hb,'sales-orders/'+order['id']+'/confirm').status_code==200
    supplier=post(c,hb,'suppliers',{'supplier_code':'B-SUP','name':'Private supplier B'})
    post(c,hb,'purchase-orders',{'po_code':'B-PO','supplier_id':supplier['id'],'lines':[{'line_no':1,'product_id':product_b['id'],'quantity':'2','uom':'m2','unit_price':1000}]})
    inv=invoice(c,hb,customer,code='B-INV')
    receipt_b=post(c,hb,'customer-receipts',{'receipt_code':'B-PT','customer_id':customer['id'],'amount':1000,'payment_method':'cash'})
    post(c,hb,'tasks',{'task_code':'B-TASK','title':'Private task','assignee_ids':[b['employee_id']]})
    post(c,hb,'kpi-targets',{'employee_id':b['employee_id'],'kpi_type':'sales_revenue','target_amount':2000,'period_start':'2026-10-01','period_end':'2026-10-31'})
    tested=0
    with c.app.state.engine.begin() as conn:
        ids={name:conn.execute(sa.select(md.tables[name].c.id).where(md.tables[name].c.organization_id==b['organization_id']).limit(1)).scalar_one_or_none() for name in NAMES}
    for name,path in NAMES.items():
        listing=c.get('/api/v1/'+path,headers=ha);assert listing.status_code==200,listing.text
        assert all(row['organization_id']==a['organization_id'] for row in listing.json()['items'])
        if ids[name]:
            assert c.get('/api/v1/'+path+'/'+ids[name],headers=ha).status_code==404,(name,ids[name])
            tested+=1
    assert tested>=15
    malicious={'order_code':'BAD','customer_id':customer['id'],'lines':[{'line_no':1,'product_id':product_b['id'],'quantity':'1','uom':'m2','unit_price':1}]}
    assert c.post('/api/v1/sales-orders',headers=ha,json=malicious).status_code==404
    assert c.patch('/api/v1/customers/'+customer['id'],headers=ha,json={'name':'Overwrite'}).status_code==404
    assert action(c,ha,'inventory-movements/issue',{'inventory_unit_id':u['inventory_unit_id'],'quantity':'1','reason':'Cross tenant attempt'}).status_code==404
    assert action(c,ha,'customer-receipts/'+receipt_b['id']+'/verify').status_code==404
