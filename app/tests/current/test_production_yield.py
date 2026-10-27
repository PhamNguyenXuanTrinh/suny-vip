from decimal import Decimal
import pytest
from .conftest import add_user
from .test_business import post,product
from .test_inventory import action,warehouse,receipt


def prepare(erp):
    c,login,a,b=erp;h=login();fg=product(c,h);raw=product(c,h,'RAW');w=warehouse(c,h);receipt(c,h,raw,w,'100')
    wc=post(c,h,'work-centers',{'site_id':w['site_id'],'code':'WC','name':'Line'})
    bom=post(c,h,'boms',{'bom_code':'BOM','product_id':fg['id'],'output_quantity':'1','lines':[{'line_no':1,'component_product_id':raw['id'],'quantity':'1','uom':'m2'}]})
    assert action(c,h,'boms/'+bom['id']+'/activate').status_code==200
    order=post(c,h,'production-orders',{'production_order_code':'YIELD','product_id':fg['id'],'bom_id':bom['id'],'planned_quantity':'10','lines':[{'sequence_no':1,'work_center_id':wc['id']},{'sequence_no':2,'work_center_id':wc['id']}]})
    ops=sorted(c.get('/api/v1/production-orders/'+order['id'],headers=h).json()['lines'],key=lambda r:r['sequence_no'])
    assert action(c,h,'production-orders/'+order['id']+'/release',{'warehouse_id':w['id']}).status_code==200
    assert action(c,h,'production-orders/'+order['id']+'/start').status_code==200
    return c,h,order,w,ops


def test_each_operation_can_only_receive_previous_good_quantity(erp):
    c,h,order,w,ops=prepare(erp);path='production-orders/'+order['id']
    assert action(c,h,path+'/reports',{'operation_id':ops[0]['id'],'good_quantity':'9','scrap_quantity':'1','downtime_minutes':5,'downtime_reason':'Vệ sinh máy'}).status_code==200
    assert action(c,h,path+'/reports',{'operation_id':ops[1]['id'],'good_quantity':'10'}).status_code==409
    assert action(c,h,path+'/reports',{'operation_id':ops[1]['id'],'good_quantity':'7','scrap_quantity':'2','downtime_minutes':3,'downtime_reason':'Đổi cuộn'}).status_code==200
    detail=c.get('/api/v1/'+path,headers=h).json();assert (Decimal(detail['good_quantity']),Decimal(detail['scrap_quantity']))==(7,3)
    summary=c.get('/api/v1/reports/production',headers=h).json();assert summary['total_downtime_minutes']==8 and summary['items'][0]['downtime_minutes']==8
    result=action(c,h,path+'/complete',{'warehouse_id':w['id']});assert result.status_code==200,result.text
    assert Decimal(result.json()['output']['remaining_quantity'])==7


def test_all_scrap_closes_downstream_without_fake_stock(erp):
    c,h,order,w,ops=prepare(erp);path='production-orders/'+order['id']
    assert action(c,h,path+'/reports',{'operation_id':ops[0]['id'],'scrap_quantity':'10'}).status_code==200
    detail=c.get('/api/v1/'+path,headers=h).json();assert all(op['status']=='completed' for op in detail['lines'])
    assert c.get('/api/v1/production-reports',headers=h).json()['total']==1
    result=action(c,h,path+'/complete',{'warehouse_id':w['id']});assert result.status_code==200,result.text
    assert not result.json().get('output') and result.json()['rounding_variance_vnd']==0 and result.json()['scrap_material_cost_vnd']>0


@pytest.mark.parametrize('first_good,first_scrap,delta_good,delta_scrap,next_good,next_scrap',[('9','1','-1','1','7','1'),('0','10','1','-1','1','0')])
def test_correction_updates_next_operation_capacity_and_reopens_zero_input(erp,first_good,first_scrap,delta_good,delta_scrap,next_good,next_scrap):
    c,h,order,w,ops=prepare(erp);path='production-orders/'+order['id']
    report=action(c,h,path+'/reports',{'operation_id':ops[0]['id'],'good_quantity':first_good,'scrap_quantity':first_scrap});assert report.status_code==200
    assert action(c,h,'production-reports/'+report.json()['id']+'/corrections',{'good_delta':delta_good,'scrap_delta':delta_scrap,'reason':'Đối chiếu biên bản chất lượng'}).status_code==200
    assert action(c,h,path+'/reports',{'operation_id':ops[1]['id'],'good_quantity':str(Decimal(next_good)+Decimal(next_scrap)+1)}).status_code==409
    assert action(c,h,path+'/reports',{'operation_id':ops[1]['id'],'good_quantity':next_good,'scrap_quantity':next_scrap}).status_code==200
    result=action(c,h,path+'/complete',{'warehouse_id':w['id']});assert result.status_code==200,result.text
    assert Decimal(result.json()['output']['remaining_quantity'])==Decimal(next_good)


def test_mixed_worker_and_site_qc_grants_keep_assignment_scope(erp):
    c,h,order,w,ops=prepare(erp);_,login,a,b=erp
    other=warehouse(c,h,'OTHER');wc=post(c,h,'work-centers',{'site_id':other['site_id'],'code':'OTHER','name':'Other'})
    hidden=post(c,h,'production-orders',{'production_order_code':'OTHER','product_id':order['product_id'],'bom_id':order['bom_id'],'planned_quantity':'1','lines':[{'sequence_no':1,'work_center_id':wc['id']}]})
    uid,eid=add_user(c,a['organization_id'],'mixed_worker','WORKER')
    assert c.post('/api/v1/users/'+uid+'/roles',headers=h,json={'grants':[{'code':'WORKER'},{'code':'QC_LEADER','site_id':w['site_id']}]}).status_code==200
    mh=login('mixed_worker')
    assert c.get('/api/v1/production-orders/'+order['id'],headers=mh).status_code==200
    assert c.get('/api/v1/production-orders/'+hidden['id'],headers=mh).status_code==404
    post(c,h,'tasks',{'task_code':'CROSS-SITE-ASSIGNED','title':'Assigned by global manager','production_order_id':hidden['id'],'assignee_ids':[eid]})
    assert c.get('/api/v1/production-orders/'+hidden['id'],headers=mh).status_code==200
