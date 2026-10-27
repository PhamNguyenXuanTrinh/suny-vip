from datetime import timedelta
from decimal import Decimal
import json,os,uuid
import sqlalchemy as sa
from fastapi import APIRouter,Request
from backend.app.models import metadata as md
from backend.app.models.base import utcnow
from backend.app.core.clock import business_today
from backend.app.core.security import current,Principal
from backend.app.services.reports import kpi_progress
from backend.app.services.auth import audit

router=APIRouter(prefix='/api/v1',tags=['Rule-based alerts'])

def notification(c,p,title,content,kind='warning',dedupe_key=None):
    t=md.tables['notifications'];now=utcnow()
    if dedupe_key:
        for old in c.execute(sa.select(t.c.content).where(t.c.organization_id==p.organization_id,t.c.user_id==p.user_id,t.c.created_at>=now-timedelta(hours=24))).scalars():
            try:
                if json.loads(old).get('dedupe_key')==dedupe_key:return None
            except (ValueError,AttributeError):pass
    rid=str(uuid.uuid4());data={**content,'generated_at':now.isoformat()}
    if dedupe_key:data['dedupe_key']=dedupe_key
    c.execute(t.insert().values(id=rid,organization_id=p.organization_id,user_id=p.user_id,title=title,content=json.dumps(data,ensure_ascii=False),type=kind,is_read=False))
    return rid

def anomalies(c,p):
    p.require('inventory.read');t=md.tables['inventory_movements'];products=md.tables['products']
    from backend.app.core.tenancy import scope
    config=json.loads(os.getenv('SUNNY_RECEIPT_SPIKE_THRESHOLDS','{}'));now=utcnow();items=[]
    for sku,cfg in config.items():
        prod=c.execute(sa.select(products).where(products.c.organization_id==p.organization_id,products.c.sku==sku)).mappings().first()
        if not prod:continue
        days=max(2,min(int(cfg.get('baseline_days',14)),90));factor=Decimal(str(cfg.get('factor',3)));minimum=Decimal(str(cfg.get('minimum_quantity',100)))
        rows=c.execute(sa.select(t).where(scope('inventory_movements',p,'inventory.read'),t.c.product_id==prod['id'],t.c.movement_type=='receipt',t.c.occurred_at>=now-timedelta(days=days+1))).mappings().all()
        recent=[r for r in rows if r['occurred_at']>=now-timedelta(days=1)]
        actual=sum((r['quantity_delta'] for r in recent),Decimal(0));baseline=sum((r['quantity_delta'] for r in rows if r not in recent),Decimal(0))/days
        threshold=max(minimum,baseline*factor)
        if actual>threshold:items.append({'rule':'receipt_spike','sku':sku,'uom':prod['base_uom'],'actual_quantity':str(actual),'baseline_daily_quantity':str(baseline),'baseline_days':days,'threshold':str(threshold),'movement_ids':[r['id'] for r in recent][:50]})
    return {'items':items,'configured_skus':list(config),'generated_at':now.isoformat(),'source_tables':['inventory_movements']}

def evaluate(c,p):
    p.require('jobs.run');created=[];today=business_today(utcnow())
    for r in kpi_progress(c,p)['items']:
        if r['status']!='active' or not date_value(r['period_start'])<=today<=date_value(r['period_end']):continue
        if r['achieved']:continue
        target=Decimal(str(r['target_amount'] if r['target_amount'] is not None else r['target_value']))
        if r['direction']=='at_least':
            elapsed=Decimal((today-date_value(r['period_start'])).days+1)/Decimal((date_value(r['period_end'])-date_value(r['period_start'])).days+1)
            if Decimal(r['actual_value'])>=target*elapsed*Decimal('0.8'):continue
        rid=notification(c,p,'KPI cần theo dõi',{'rule':'kpi_behind','kpi_id':r['id'],'actual':r['actual_value'],'target':str(target),'unit':r['unit'],'period_start':r['period_start'],'period_end':r['period_end'],'source_tables':r['source_tables']},dedupe_key='kpi:'+r['id'])
        if rid:created.append(rid)
    for item in anomalies(c,p)['items']:
        rid=notification(c,p,'Nhập kho vượt ngưỡng',item,dedupe_key='spike:'+item['sku'])
        if rid:created.append(rid)
    audit(c,p,'evaluate_alerts','notifications',data={'created':len(created)})
    return {'created_count':len(created),'notification_ids':created,'source':'configured_rules_and_business_records'}

def date_value(s):
    from datetime import date
    return date.fromisoformat(s)

def evaluate_all(engine):
    with engine.begin() as c:
        users=md.tables['app_users'];roles=md.tables['roles'];grants=md.tables['user_roles'];org=md.tables['organizations']
        employees=md.tables['employees']
        rows=c.execute(sa.select(users).join(grants,grants.c.user_id==users.c.id).join(roles,roles.c.id==grants.c.role_id).join(org,org.c.id==users.c.organization_id).join(employees,employees.c.id==users.c.employee_id).where(users.c.is_active.is_(True),roles.c.code=='ADMIN',roles.c.is_active.is_(True),grants.c.site_id.is_(None),org.c.is_active.is_(True),employees.c.status=='active')).mappings().all()
        for u in rows:
            p=Principal(u['id'],u['organization_id'],u['employee_id'],u['username'],[{'code':'ADMIN','site_id':None}],'system-job',False)
            evaluate(c,p)

@router.post('/system/evaluate-alerts')
def run(request:Request):
    with request.app.state.engine.begin() as c:return evaluate(c,current(c,request))
