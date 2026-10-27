import uuid
from decimal import Decimal
from .conftest import add_user
from .test_business import post,product
from .test_inventory import action,warehouse,receipt

def test_production_from_bom_to_inventory_with_assigned_worker(erp):
    c,login,a,b=erp;h=login();fg=product(c,h);raw=product(c,h,'RAW');w=warehouse(c,h);receipt(c,h,raw,w,'100')
    wc=post(c,h,'work-centers',{'site_id':w['site_id'],'code':'LINE1','name':'Dây chuyền 1'})
    bom=post(c,h,'boms',{'bom_code':'BOM1','product_id':fg['id'],'output_quantity':'1','lines':[{'line_no':1,'component_product_id':raw['id'],'quantity':'2','uom':'m2','scrap_rate':0}]})
    assert action(c,h,'boms/'+bom['id']+'/activate').status_code==200
    order=post(c,h,'production-orders',{'production_order_code':'SX1','product_id':fg['id'],'bom_id':bom['id'],'planned_quantity':'10','lines':[{'sequence_no':1,'work_center_id':wc['id']}]})
    op=c.get('/api/v1/production-orders/'+order['id'],headers=h).json()['lines'][0]['id']
    uid,eid=add_user(c,a['organization_id'],'worker','WORKER');wh=login('worker')
    assert action(c,wh,'production-orders/'+order['id']+'/start').status_code==404
    task=post(c,h,'tasks',{'task_code':'TASK1','title':'Sản xuất lệnh SX1','production_order_id':order['id'],'assignee_ids':[eid]})
    assert action(c,h,'production-orders/'+order['id']+'/release',{'warehouse_id':w['id']}).status_code==200
    assert action(c,wh,'production-orders/'+order['id']+'/start').status_code==200
    report={'operation_id':op,'good_quantity':'9','scrap_quantity':'1','downtime_minutes':5,'downtime_reason':'Vệ sinh máy'}
    key=str(uuid.uuid4());r=action(c,wh,'production-orders/'+order['id']+'/reports',report,key);assert r.status_code==200,r.text
    assert action(c,wh,'production-orders/'+order['id']+'/reports',report,key).json()==r.json()
    assert action(c,wh,'production-orders/'+order['id']+'/reports',report).status_code==409
    r=action(c,h,'production-orders/'+order['id']+'/complete',{'warehouse_id':w['id']});assert r.status_code==200,r.text
    output=c.get('/api/v1/inventory-units/'+r.json()['output']['inventory_unit_id'],headers=h).json()
    assert Decimal(output['remaining_quantity'])==9
    assert output['unit_cost']==22224
    assert r.json()['material_cost_vnd']==200020 and r.json()['rounding_variance_vnd']==4
    movements=c.get('/api/v1/inventory-movements',headers=h).json()['items']
    assert sum(Decimal(m['quantity_delta']) for m in movements if m['product_id']==raw['id'])==80
    assert action(c,wh,'tasks/'+task['id']+'/updates',{'status':'in_progress','content':'Đã chạy máy','progress_percent':50}).status_code==200
    assert action(c,wh,'tasks/'+task['id']+'/updates',{'status':'completed','content':'Đã hoàn thành','progress_percent':100}).status_code==200
    assert c.patch('/api/v1/boms/'+bom['id'],headers=h,json={'output_quantity':'2'}).status_code==409

def test_bom_cycle_and_material_shortage_roll_back(erp):
    c,login,a,b=erp;h=login();p=product(c,h);w=warehouse(c,h)
    bom=post(c,h,'boms',{'bom_code':'CYCLE','product_id':p['id'],'output_quantity':'1','lines':[{'line_no':1,'component_product_id':p['id'],'quantity':'1','uom':'m2'}]})
    assert action(c,h,'boms/'+bom['id']+'/activate').status_code==422
    raw=product(c,h,'RAW');bom=post(c,h,'boms',{'bom_code':'OK','product_id':p['id'],'output_quantity':'1','lines':[{'line_no':1,'component_product_id':raw['id'],'quantity':'2','uom':'m2'}]})
    assert action(c,h,'boms/'+bom['id']+'/activate').status_code==200
    wc=post(c,h,'work-centers',{'code':'WC','name':'Line','site_id':w['site_id']})
    order=post(c,h,'production-orders',{'production_order_code':'SHORT','product_id':p['id'],'bom_id':bom['id'],'planned_quantity':'10','lines':[{'sequence_no':1,'work_center_id':wc['id']}]})
    assert action(c,h,'production-orders/'+order['id']+'/release',{'warehouse_id':w['id']}).status_code==409
    assert c.get('/api/v1/production-orders/'+order['id'],headers=h).json()['status']=='draft'
    assert c.get('/api/v1/inventory-movements',headers=h).json()['total']==0
