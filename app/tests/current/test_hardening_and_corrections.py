from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import json,os,subprocess,sys,uuid
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
import pytest
from backend.app.models import metadata as md
from backend.scripts.check_db_integrity import check
from .conftest import add_user
from .test_business import post,product
from .test_inventory import action,warehouse,receipt
from .test_finance import invoice

def test_eight_users_write_stock_without_lost_updates(erp):
    c,login,a,b=erp;h=login();p=product(c,h);w=warehouse(c,h);u=receipt(c,h,p,w,'100')
    headers=[]
    for i in range(8):
        add_user(c,a['organization_id'],'qc_load_'+str(i),'QC_LEADER');headers.append(login('qc_load_'+str(i)))
    def work(h):
        return [action(c,h,'inventory-movements/issue',{'inventory_unit_id':u['inventory_unit_id'],'quantity':'1','reason':'Xuất kiểm thử đồng thời'}).status_code for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(work,headers))
    assert all(status==200 for batch in results for status in batch)
    assert Decimal(c.get('/api/v1/inventory-units/'+u['inventory_unit_id'],headers=h).json()['remaining_quantity'])==36
    assert check(c.app.state.settings.database_path)['passed']

def test_eight_finance_requests_cannot_overallocate(erp):
    c,login,a,b=erp;h=login();customer=post(c,h,'customers',{'customer_code':'KH','name':'Customer'});inv=invoice(c,h,customer,amount=10000)
    r=post(c,h,'customer-receipts',{'receipt_code':'PT','customer_id':customer['id'],'amount':10000,'payment_method':'cash'});assert action(c,h,'customer-receipts/'+r['id']+'/verify').status_code==200
    headers=[]
    for i in range(8):add_user(c,a['organization_id'],'finance_load_'+str(i),'ACCOUNTANT');headers.append(login('finance_load_'+str(i)))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda auth:action(c,auth,'customer-receipts/'+r['id']+'/allocations',{'invoice_id':inv['id'],'amount':1500}),headers))
    assert sorted(r.status_code for r in results)==[200]*6+[409]*2
    with c.app.state.engine.begin() as conn:assert conn.exec_driver_sql('SELECT SUM(amount) FROM payment_allocation_events').scalar_one()==9000
    assert check(c.app.state.settings.database_path)['passed']

def test_full_roll_transfer_preserves_its_physical_code(erp):
    c,login,a,b=erp;h=login();p=product(c,h);w=warehouse(c,h);w2=warehouse(c,h,'W2');u=receipt(c,h,p,w,'10')
    before=c.get('/api/v1/inventory-units/'+u['inventory_unit_id'],headers=h).json()
    transfer=post(c,h,'stock-transfers',{'transfer_code':'FULL','from_warehouse_id':w['id'],'to_warehouse_id':w2['id'],'lines':[{'product_id':p['id'],'inventory_unit_id':u['inventory_unit_id'],'quantity':'10','uom':'m2'}]})
    assert action(c,h,'stock-transfers/'+transfer['id']+'/ship').status_code==200
    assert c.get('/api/v1/inventory-units/'+u['inventory_unit_id'],headers=h).json()['status']=='in_transit'
    r=action(c,h,'stock-transfers/'+transfer['id']+'/receive');assert r.status_code==200,r.text
    assert r.json()['receipts'][0]['inventory_unit_id']==u['inventory_unit_id']
    after=c.get('/api/v1/inventory-units/'+u['inventory_unit_id'],headers=h).json()
    assert after['roll_code']==before['roll_code'] and after['warehouse_id']==w2['id']
    assert check(c.app.state.settings.database_path)['passed']

def test_production_correction_preserves_original_and_reconciles_output(erp):
    c,login,a,b=erp;h=login();fg=product(c,h);raw=product(c,h,'RAW');w=warehouse(c,h);receipt(c,h,raw,w,'100')
    wc=post(c,h,'work-centers',{'site_id':w['site_id'],'code':'WC','name':'Line'})
    bom=post(c,h,'boms',{'bom_code':'BOM','product_id':fg['id'],'output_quantity':'1','lines':[{'line_no':1,'component_product_id':raw['id'],'quantity':'2','uom':'m2'}]})
    assert action(c,h,'boms/'+bom['id']+'/activate').status_code==200
    order=post(c,h,'production-orders',{'production_order_code':'SX','product_id':fg['id'],'bom_id':bom['id'],'planned_quantity':'5','lines':[{'sequence_no':1,'work_center_id':wc['id']}]})
    op=c.get('/api/v1/production-orders/'+order['id'],headers=h).json()['lines'][0]['id']
    assert action(c,h,'production-orders/'+order['id']+'/release',{'warehouse_id':w['id']}).status_code==200
    assert action(c,h,'production-orders/'+order['id']+'/start').status_code==200
    report=action(c,h,'production-orders/'+order['id']+'/reports',{'operation_id':op,'good_quantity':'4','scrap_quantity':'1'}).json()
    body={'good_delta':'-1','scrap_delta':'1','reason':'Đối chiếu lại biên bản QC'};key=str(uuid.uuid4())
    fix=action(c,h,'production-reports/'+report['id']+'/corrections',body,key);assert fix.status_code==200,fix.text
    assert action(c,h,'production-reports/'+report['id']+'/corrections',body,key).json()==fix.json()
    original=c.get('/api/v1/production-reports/'+report['id'],headers=h).json()
    assert Decimal(original['good_quantity'])==4 and len(original['corrections'])==1
    assert action(c,h,'production-reports/'+report['id']+'/corrections',{**body,'good_delta':'-99'}).status_code==409
    result=action(c,h,'production-orders/'+order['id']+'/complete',{'warehouse_id':w['id']});assert result.status_code==200,result.text
    assert Decimal(result.json()['output']['remaining_quantity'])==3
    assert action(c,h,'production-reports/'+report['id']+'/corrections',body).status_code==409
    with pytest.raises(IntegrityError),c.app.state.engine.begin() as conn:conn.exec_driver_sql('DELETE FROM production_report_corrections')
    from backend.app.core.clock import business_today
    today=business_today().isoformat()
    post(c,h,'kpi-targets',{'employee_id':a['employee_id'],'kpi_type':'output_quantity','target_value':'5','period_start':today,'period_end':today})
    assert c.get('/api/v1/kpi-progress',headers=h).json()['items'][0]['actual_value']=='3.000000'
    assert check(c.app.state.settings.database_path)['passed']

def test_clean_setup_needs_no_api_key_and_preserves_existing_config(tmp_path):
    root=Path(__file__).resolve().parents[2];config=tmp_path/'private.env';data=tmp_path/'runtime';env=dict(os.environ)
    for k in ('SUNNY_ERP_DB','SUNNY_JWT_SECRET','SUNNY_UPLOAD_DIR','DATABASE_URL','OPENAI_API_KEY'):env.pop(k,None)
    command=[sys.executable,'-m','backend.scripts.setup_local','--config',str(config),'--data-dir',str(data),'--no-admin']
    first=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True);assert first.returncode==0,first.stderr
    contents=config.read_bytes()
    second=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True);assert second.returncode==0,second.stderr
    assert config.read_bytes()==contents
    assert json.loads(first.stdout)['openai_required'] is False
    verified=subprocess.run([sys.executable,'-m','backend.scripts.run_server','--config',str(config),'--check'],cwd=root,env=env,capture_output=True,text=True)
    assert verified.returncode==0,verified.stderr
    assert json.loads(verified.stdout)['configured'] is True
