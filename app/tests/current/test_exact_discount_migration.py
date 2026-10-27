from datetime import date
from decimal import Decimal
import sqlite3
import pytest
import sqlalchemy as sa
from backend.app.database import make_engine,verify_database
from backend.app.models import metadata as md
from backend.scripts.migrate_db import migrate
from .test_business import post,product
from .test_database_contract import insert,organization,employee,user

@pytest.mark.parametrize('quantity,price,gross',[('0.5',100001,50001),('0.000001',500000,1),('999999.999999',999999999,999999998999000)])
def test_discount_uses_exact_half_up_vnd(erp,quantity,price,gross):
    c,login,*_=erp;h=login();p=product(c,h);customer=post(c,h,'customers',{'customer_code':'ROUND','name':'Round'})
    body={'order_code':'ROUND','customer_id':customer['id'],'lines':[{'line_no':1,'product_id':p['id'],'quantity':quantity,'uom':'m2','unit_price':price,'discount_amount':gross}]}
    order=post(c,h,'sales-orders',body);assert order['subtotal_amount']==gross and order['total_amount']==0
    body['order_code']='OVER';body['lines'][0]['discount_amount']=gross+1
    assert c.post('/api/v1/sales-orders',headers=h,json=body).status_code==422


def test_nonempty_upgrade_keeps_line_ids_foreign_keys_and_backup(tmp_path):
    path=tmp_path/'old.sqlite3';migrate(path,'0006_production_corrections');engine=make_engine('sqlite:///'+str(path))
    with engine.begin() as c:
        org=organization(c);actor=user(c,org,employee(c,org));customer=insert(c,'customers',organization_id=org,customer_code='C',name='C');prod=insert(c,'products',organization_id=org,sku='P',name='P',base_uom='m2')
        order=insert(c,'sales_orders',organization_id=org,order_code='S',customer_id=customer,created_by=actor)
        line=insert(c,'sales_order_lines',organization_id=org,order_id=order,line_no=1,product_id=prod,quantity=Decimal('0.5'),uom='m2',unit_price=100001)
        inv=insert(c,'customer_invoices',organization_id=org,invoice_no='I',customer_id=customer,invoice_date=date(2026,10,26))
        linked=insert(c,'customer_invoice_lines',organization_id=org,invoice_id=inv,sales_order_line_id=line,line_no=1,quantity=Decimal('0.5'),uom='m2',unit_price=100001)
    with pytest.raises(sa.exc.IntegrityError),engine.begin() as c:c.execute(md.tables['sales_order_lines'].update().where(md.tables['sales_order_lines'].c.id==line).values(discount_amount=50001))
    engine.dispose();result=migrate(path);assert result['backup'] and verify_database(path)=={'integrity':'ok','foreign_key_errors':[]}
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT sales_order_line_id FROM customer_invoice_lines WHERE id=?',(linked,)).fetchone()==(line,)
        c.execute('UPDATE sales_order_lines SET discount_amount=50001 WHERE id=?',(line,))
        assert c.execute('SELECT COUNT(*) FROM sales_order_lines').fetchone()==(1,)
