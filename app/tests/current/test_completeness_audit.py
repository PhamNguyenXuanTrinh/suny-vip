from pathlib import Path
from dataclasses import replace
from decimal import Decimal
import io,json,re,uuid
import pytest
import sqlalchemy as sa
from PIL import Image
from backend.app.models import metadata as md
from .conftest import add_user
from .test_business import post,product
from .test_inventory import action,warehouse,receipt
from .test_finance import invoice


def test_all_documented_api_methods_exist(erp):
    c,*_=erp;normalize=lambda p:re.sub(r'\{[^}]+\}','{}',p)
    required=json.loads((Path(__file__).resolve().parents[2]/'docs/current/required_api_contract.json').read_text())['methods']
    actual={(m.upper(),normalize(p)) for p,ops in c.get('/api/openapi.json').json()['paths'].items() for m in ops}
    assert len(required)==102
    assert {(r['method'],normalize(r['path'])) for r in required}<=actual


def test_mixed_global_ctv_and_site_admin_do_not_expand_grants(erp):
    c,login,a,b=erp;h=login();s1=post(c,h,'sites',{'code':'A','name':'A'});s2=post(c,h,'sites',{'code':'B','name':'B'})
    uid,eid=add_user(c,a['organization_id'],'mixed','CTV',s1['id'])
    _,ea=add_user(c,a['organization_id'],'worker_a','SALES',s1['id']);_,eb=add_user(c,a['organization_id'],'worker_b','SALES',s2['id'])
    assert c.post('/api/v1/users/'+uid+'/roles',headers=h,json={'grants':[{'code':'CTV'},{'code':'ADMIN','site_id':s1['id']}]}).status_code==200
    own=post(c,h,'customers',{'customer_code':'OWN','name':'Own','owner_employee_id':eid})
    local=post(c,h,'customers',{'customer_code':'LOCAL','name':'Local','owner_employee_id':ea})
    foreign=post(c,h,'customers',{'customer_code':'OTHER','name':'Other','owner_employee_id':eb})
    mh=login('mixed')
    assert {r['id'] for r in c.get('/api/v1/customers',headers=mh).json()['items']}=={own['id'],local['id']}
    assert c.get('/api/v1/customers/'+foreign['id'],headers=mh).status_code==404
    assert c.post('/api/v1/users/'+uid+'/roles',headers=mh,json={'grants':[{'code':'ADMIN'}]}).status_code==403
    post(c,h,'kpi-targets',{'employee_id':eb,'kpi_type':'output_quantity','target_value':'100','period_start':'2026-10-01','period_end':'2026-10-31'})
    assert c.get('/api/v1/kpi-targets',headers=mh).json()['total']==0
    stream=io.BytesIO();Image.new('RGB',(2,2)).save(stream,'PNG')
    doc=c.post('/api/v1/documents',headers=h,files={'file':('private.png',stream.getvalue(),'image/png')}).json()
    assert c.get('/api/v1/documents/'+doc['id']+'/download',headers=mh).status_code==404


def test_task_reassignment_replaces_access_and_preserves_history(erp):
    c,login,a,b=erp;h=login();_,e1=add_user(c,a['organization_id'],'old','WORKER');_,e2=add_user(c,a['organization_id'],'new','WORKER')
    task=post(c,h,'tasks',{'task_code':'REASSIGN','title':'Shift','assignee_ids':[e1]})
    path='tasks/'+task['id']+'/assignees';body={'employee_ids':[e2],'reason':'Đổi ca làm việc'};key=str(uuid.uuid4())
    result=action(c,h,path,body,key);assert result.status_code==200,result.text
    assert action(c,h,path,body,key).json()==result.json()
    assert c.get('/api/v1/tasks/'+task['id'],headers=login('old')).status_code==404
    detail=c.get('/api/v1/tasks/'+task['id'],headers=login('new')).json()
    assert detail['assignee_ids']==[e2]
    assert {(r['employee_id'],r['status']) for r in detail['assignees']}=={(e1,'removed'),(e2,'assigned')}
    _,foreign=add_user(c,b['organization_id'],'foreign','WORKER')
    assert action(c,h,path,{'employee_ids':[foreign]}).status_code==404
    assert c.get('/api/v1/tasks/'+task['id'],headers=h).json()['assignee_ids']==[e2]


def test_change_primary_contact_and_clear_nullable_fields(erp):
    c,login,*_=erp;h=login();customer=post(c,h,'customers',{'customer_code':'CONTACT','name':'C','phone':'123'})
    one=post(c,h,'customer-contacts',{'customer_id':customer['id'],'full_name':'One','is_primary':True});two=post(c,h,'customer-contacts',{'customer_id':customer['id'],'full_name':'Two'})
    assert c.patch('/api/v1/customer-contacts/'+two['id'],headers=h,json={'is_primary':True}).status_code==200
    assert c.get('/api/v1/customer-contacts/'+one['id'],headers=h).json()['is_primary'] is False
    assert c.patch('/api/v1/customers/'+customer['id'],headers=h,json={'phone':None}).status_code==200
    assert c.get('/api/v1/customers/'+customer['id'],headers=h).json()['phone'] is None


@pytest.mark.parametrize('kind',['receipt','payment'])
def test_zero_money_rejected_with_field_error(erp,kind):
    c,login,*_=erp;h=login();supplier=kind=='payment'
    party=post(c,h,'suppliers' if supplier else 'customers',{'supplier_code' if supplier else 'customer_code':'ZERO','name':'Zero'})
    path='supplier-payments' if supplier else 'customer-receipts'
    result=c.post('/api/v1/'+path,headers=h,json={'payment_code' if supplier else 'receipt_code':'ZERO','supplier_id' if supplier else 'customer_id':party['id'],'amount':0,'payment_method':'cash'})
    assert result.status_code==422
    assert result.json()['error']['fields'][0]['field']=='amount'
    assert c.get('/api/v1/'+path,headers=h).json()['total']==0


def test_invoice_cannot_double_bill_or_change_source_uom(erp):
    c,login,*_=erp;h=login();p=product(c,h);customer=post(c,h,'customers',{'customer_code':'BILL','name':'Bill'})
    order=post(c,h,'sales-orders',{'order_code':'BILL','customer_id':customer['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':'10','uom':'m2','unit_price':1000}]})
    assert action(c,h,'sales-orders/'+order['id']+'/confirm').status_code==200
    line=c.get('/api/v1/sales-orders/'+order['id'],headers=h).json()['lines'][0]
    def make(code,quantity,uom='m2'):
        return post(c,h,'customer-invoices',{'invoice_no':code,'customer_id':customer['id'],'sales_order_id':order['id'],'invoice_date':'2026-10-26','lines':[{'line_no':1,'sales_order_line_id':line['id'],'quantity':quantity,'uom':uom,'unit_price':1000}]})
    first=make('ONE','6');assert action(c,h,'customer-invoices/'+first['id']+'/issue').status_code==200
    second=make('TWO','6');assert action(c,h,'customer-invoices/'+second['id']+'/issue').status_code==409
    wrong=make('UOM','1','kg');assert action(c,h,'customer-invoices/'+wrong['id']+'/issue').status_code==422
    final=make('REST','4');assert action(c,h,'customer-invoices/'+final['id']+'/issue').status_code==200


def test_allocations_detail_and_manual_issue_reason(erp):
    c,login,*_=erp;h=login();customer=post(c,h,'customers',{'customer_code':'AR','name':'AR'});inv=invoice(c,h,customer,amount=10000)
    pay=post(c,h,'customer-receipts',{'receipt_code':'AR','customer_id':customer['id'],'amount':8000,'payment_method':'cash'})
    assert action(c,h,'customer-receipts/'+pay['id']+'/verify').status_code==200
    assert action(c,h,'customer-receipts/'+pay['id']+'/allocations',{'invoice_id':inv['id'],'amount':6000}).status_code==200
    assert c.get('/api/v1/customer-invoices/'+inv['id'],headers=h).json()['outstanding_amount']==4000
    detail=c.get('/api/v1/customer-receipts/'+pay['id'],headers=h).json()
    assert detail['unallocated_amount']==2000 and detail['allocations'][0]['amount']==6000
    p=product(c,h);w=warehouse(c,h);unit=receipt(c,h,p,w,'3');reason='Xuất mẫu kiểm tra chất lượng'
    assert action(c,h,'inventory-movements/issue',{'inventory_unit_id':unit['inventory_unit_id'],'quantity':'1','reason':reason}).status_code==200
    assert any(reason in (r['new_json'] or '') for r in c.get('/api/v1/audit-log?page_size=100',headers=h).json()['items'])


def test_sessions_cap_rotation_and_own_only_revocation(erp):
    c,login,a,b=erp;c.app.state.settings=replace(c.app.state.settings,max_sessions=2)
    first=login();second=login();third=login()
    assert c.get('/api/v1/auth/me',headers=first).status_code==401
    sessions=c.get('/api/v1/auth/sessions',headers=third).json();assert len(sessions['items'])==2
    other=next(r for r in sessions['items'] if not r['current'])
    assert c.post('/api/v1/auth/sessions/'+other['id']+'/revoke',headers=login('admin_b')).status_code==404
    assert c.post('/api/v1/auth/sessions/'+other['id']+'/revoke',headers=third).status_code==200
    assert c.get('/api/v1/auth/me',headers=second).status_code==401
    assert c.get('/api/v1/auth/me',headers=third).status_code==200


def test_department_tree_and_server_filters_sort_pagination(erp):
    c,login,*_=erp;h=login();root=post(c,h,'departments',{'code':'ROOT','name':'Root'});child=post(c,h,'departments',{'code':'CHILD','name':'Child','parent_department_id':root['id']})
    tree=c.get('/api/v1/department-tree',headers=h).json();assert tree['total']==2 and tree['items'][0]['children'][0]['id']==child['id']
    for code,status in [('A','active'),('B','inactive'),('C','active')]:post(c,h,'customers',{'customer_code':code,'name':code,'status':status})
    result=c.get('/api/v1/customers?status=active&sort=customer_code&direction=desc&page_size=1',headers=h).json()
    assert result['total']==2 and result['items'][0]['customer_code']=='C'
    assert c.get('/api/v1/customers?status=active&sort=customer_code&direction=desc&page_size=1&page=2',headers=h).json()['items'][0]['customer_code']=='A'


def test_report_pagination_keeps_full_financial_totals_and_typed_contract(erp):
    c,login,*_=erp;h=login();party=post(c,h,'customers',{'customer_code':'PAGED','name':'Paged'})
    invoice(c,h,party,'ONE',10000);invoice(c,h,party,'TWO',20000)
    first=c.get('/api/v1/reports/ar-aging?page_size=1',headers=h).json();second=c.get('/api/v1/reports/ar-aging?page_size=1&page=2',headers=h).json()
    assert first['total_items']==second['total_items']==2
    assert first['total_outstanding']==second['total_outstanding']==30000
    assert len(first['items'])==len(second['items'])==1 and first['items'][0]['id']!=second['items'][0]['id']
    assert c.get('/api/v1/reports/ar-aging?page_size=101',headers=h).status_code==422
    schema=c.get('/api/openapi.json').json()
    assert schema['paths']['/api/v1/reports/ar-aging']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/AgingReport')


def test_document_upload_alias_shares_the_same_rate_limit(erp):
    c,login,*_=erp;h=login();stream=io.BytesIO();Image.new('RGB',(2,2)).save(stream,'PNG')
    for index in range(20):
        path='/api/v1/documents'+('/upload' if index%2 else '')
        result=c.post(path,headers=h,files={'file':('small.png',stream.getvalue(),'image/png')})
        assert result.status_code==201,result.text
    assert c.post('/api/v1/documents',headers=h,files={'file':('small.png',stream.getvalue(),'image/png')}).status_code==429
