from pathlib import Path
import sqlite3
import uuid
from decimal import Decimal
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, StatementError
from alembic import command
from alembic.config import Config
from backend.app.database import make_engine,backup_database,verify_database
from backend.app.models import metadata as md
from backend.scripts.migrate_db import migrate

def uid():return str(uuid.uuid4())

@pytest.fixture
def database(tmp_path):
    path=tmp_path/'contract.sqlite3'
    migrate(path)
    engine=make_engine('sqlite:///'+str(path))
    yield engine,path
    engine.dispose()

def insert(c,table_name,**kwargs):
    v={'id':uid(),**kwargs}
    c.execute(md.tables[table_name].insert().values(**v))
    return v['id']

def organization(c,code='A'):
    return insert(c,'organizations',code=code,name='Company '+code)

def employee(c,org,code='E'):
    return insert(c,'employees',organization_id=org,employee_code=code,full_name=code)

def user(c,org,emp,name='user'):
    return insert(c,'app_users',organization_id=org,employee_id=emp,username=name,password_hash='not-a-live-password')

def test_all_tables_uuid_foreign_keys_and_exact_decimal(database):
    engine,path=database
    with engine.begin() as c:
        names=set(sa.inspect(c).get_table_names())-{'alembic_version'}
        assert len(names & {'organizations','sites','departments','employees','app_users','roles','user_roles','customers','customer_contacts','products','sales_orders','sales_order_lines','shipments','shipment_lines','suppliers','purchase_orders','purchase_order_lines','supplier_bills','supplier_payments','warehouses','warehouse_locations','inventory_lots','inventory_units','inventory_movements','stock_transfers','stock_transfer_lines','bills_of_materials','bom_lines','work_centers','machines','production_orders','production_order_operations','production_reports','tasks','task_assignees','task_updates','customer_invoices','customer_invoice_lines','customer_receipts','customer_payment_allocations','documents','audit_log','kpi_targets','notifications'})==44
        assert {'inventory_movements','customer_payment_allocations','production_order_operations','warehouse_locations','user_roles'}<=names
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one()==1
        assert c.exec_driver_sql('PRAGMA journal_mode').scalar_one()=='wal'
        org=organization(c)
        prod=insert(c,'products',organization_id=org,sku='PP',name='Fabric',base_uom='m',standard_cost=25)
        site=insert(c,'sites',organization_id=org,code='BD',name='Factory')
        wh=insert(c,'warehouses',organization_id=org,site_id=site,code='W',name='Warehouse')
        roll=insert(c,'inventory_units',organization_id=org,product_id=prod,warehouse_id=wh,roll_code='R',initial_quantity=Decimal('999999.123456'),remaining_quantity=Decimal('999999.123456'),uom='m')
        actual=c.execute(sa.select(md.tables['inventory_units'].c.remaining_quantity).where(md.tables['inventory_units'].c.id==roll)).scalar_one()
        assert actual==Decimal('999999.123456')
        raw=c.exec_driver_sql('SELECT remaining_quantity,typeof(remaining_quantity) FROM inventory_units').one()
        assert raw==(999999123456,'integer')
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all()==[]

@pytest.mark.parametrize('bad', ['not-a-uuid','ABCDEFAB-CDEF-ABCD-EFAB-CDEFABCDEFAB','a'*36])
def test_uuid_rejected_in_database(database,bad):
    with pytest.raises(IntegrityError),database[0].begin() as c:
        insert(c,'organizations',id=bad,code='X',name='Invalid')

def test_cross_tenant_references_and_same_codes(database):
    with database[0].begin() as c:
        a=organization(c,'A');b=organization(c,'B')
        e=employee(c,a)
        insert(c,'customers',organization_id=a,customer_code='KH1',name='A',owner_employee_id=e)
        insert(c,'customers',organization_id=b,customer_code='KH1',name='B')
    with pytest.raises(IntegrityError),database[0].begin() as c:
        insert(c,'customers',organization_id=b,customer_code='KH2',name='B',owner_employee_id=e)

def test_money_integer_vnd_and_no_decimal_overprecision(database):
    with database[0].begin() as c:org=organization(c)
    with pytest.raises(IntegrityError),database[0].begin() as c:
        insert(c,'products',organization_id=org,sku='BAD',name='Bad',base_uom='kg',standard_cost=1.25)
    with pytest.raises(IntegrityError),database[0].begin() as c:
        insert(c,'organizations',code='USD',name='Wrong',base_currency='USD')
    with pytest.raises(StatementError),database[0].begin() as c:
        insert(c,'bills_of_materials',organization_id=org,bom_code='BAD',product_id=uid(),output_quantity=Decimal('1.0000001'))

def test_null_site_role_duplicates_are_rejected(database):
    with database[0].begin() as c:
        org=organization(c);e=employee(c,org);u=user(c,org,e)
        role=insert(c,'roles',organization_id=org,code='ADMIN',name='Admin')
        insert(c,'user_roles',organization_id=org,user_id=u,role_id=role)
    with pytest.raises(IntegrityError),database[0].begin() as c:
        insert(c,'user_roles',organization_id=org,user_id=u,role_id=role)

def test_location_cannot_belong_to_another_warehouse(database):
    with database[0].begin() as c:
        org=organization(c);site=insert(c,'sites',organization_id=org,code='S',name='Site')
        w1=insert(c,'warehouses',organization_id=org,site_id=site,code='W1',name='One')
        w2=insert(c,'warehouses',organization_id=org,site_id=site,code='W2',name='Two')
        loc=insert(c,'warehouse_locations',organization_id=org,warehouse_id=w1,code='A',name='Shelf',location_type='bin')
        product=insert(c,'products',organization_id=org,sku='PP',name='Fabric',base_uom='m')
    with pytest.raises(IntegrityError),database[0].begin() as c:
        insert(c,'inventory_units',organization_id=org,product_id=product,warehouse_id=w2,location_id=loc,roll_code='WRONG',uom='m')

def test_department_cycle_protected_in_sql(database):
    with database[0].begin() as c:
        org=organization(c);a=insert(c,'departments',organization_id=org,code='A',name='A')
        b=insert(c,'departments',organization_id=org,code='B',name='B',parent_department_id=a)
    with pytest.raises(IntegrityError),database[0].begin() as c:
        c.execute(md.tables['departments'].update().where(md.tables['departments'].c.id==a).values(parent_department_id=b))

def test_append_only_cannot_be_overridden_by_raw_sql(database):
    with database[0].begin() as c:
        org=organization(c)
        insert(c,'audit_log',organization_id=org,action='create',entity_type='test')
    for verb in ("UPDATE audit_log SET action='tampered'",'DELETE FROM audit_log'):
        with pytest.raises(IntegrityError),database[0].begin() as c:c.exec_driver_sql(verb)
    with database[0].begin() as c:
        triggers={r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'")}
        assert {'immutable_inventory_movements_update','immutable_inventory_movements_delete'}<=triggers

def test_upgrade_repeat_backup_and_restore_preserve_rows(database,tmp_path):
    engine,path=database
    with engine.begin() as c:org=organization(c)
    result=migrate(path)
    assert result['backup'] and verify_database(result['backup'])['integrity']=='ok'
    restored=tmp_path/'restored.sqlite3';backup_database(result['backup'],restored)
    with sqlite3.connect(restored) as c:assert c.execute('SELECT id FROM organizations').fetchone()[0]==org
    assert verify_database(restored)=={'integrity':'ok','foreign_key_errors':[]}

def test_incompatible_existing_database_not_reset(tmp_path):
    p=tmp_path/'legacy.sqlite3'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE customers(id TEXT PRIMARY KEY,name TEXT)')
        c.execute("INSERT INTO customers VALUES('legacy-id','Retain customer')")
    with pytest.raises(RuntimeError,match='reviewed legacy import'):migrate(p)
    with sqlite3.connect(p) as c:
        assert c.execute('SELECT * FROM customers').fetchall()==[('legacy-id','Retain customer')]
        assert {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}=={'customers'}

def test_empty_downgrade_and_nonempty_rollback_refused(database):
    engine,path=database
    cfg=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    with engine.begin() as c:
        cfg.attributes['connection']=c;command.downgrade(cfg,'base')
    migrate(path)
    with engine.begin() as c:organization(c)
    with pytest.raises(RuntimeError,match='verified SQLite backup'),engine.begin() as c:
        cfg.attributes['connection']=c;command.downgrade(cfg,'base')

def test_orm_is_mapped_to_real_migrated_tables(database):
    from sqlalchemy.orm import Session
    from backend.app.models import models
    with Session(database[0]) as s:
        org=models['organizations']();org.code='ORM';org.name='Mapped organization'
        s.add(org);s.commit()
        assert s.scalar(sa.select(models['organizations'])).code=='ORM'
