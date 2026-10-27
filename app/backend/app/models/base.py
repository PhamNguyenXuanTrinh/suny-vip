"""SQLAlchemy models built from the versioned, fully typed domain contract."""
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.orm import registry
from sqlalchemy.types import TypeDecorator
import hashlib

SCALE=Decimal('1000000')

def utcnow():
    return datetime.now(timezone.utc)

def safe_name(prefix, raw_name):
    name = f"{prefix}_{raw_name}"
    if len(name) > 63:
        h = hashlib.md5(name.encode()).hexdigest()[:8]
        name = f"{prefix}_{raw_name[:40]}_{h}"
    return name

class Quantity(TypeDecorator):
    """DECIMAL(18,6) contract; exact millionths in SQLite, never binary floats."""
    impl=sa.BigInteger
    cache_ok=True

    def process_bind_param(self, value, dialect):
        if value is None:return None
        d=Decimal(str(value))
        if not d.is_finite() or abs(d)>=Decimal('1000000000000') or d*SCALE!=(d*SCALE).to_integral_value():
            raise ValueError('Quantity must be finite DECIMAL(18,6)')
        return int(d*SCALE)

    def process_result_value(self,value,dialect):
        return Decimal(value)/SCALE if value is not None else None

class UTCDateTime(TypeDecorator):
    impl=sa.String(32)
    cache_ok=True

    def process_bind_param(self,value,dialect):
        if value is None:return None
        if isinstance(value,str):value=datetime.fromisoformat(value.replace('Z','+00:00'))
        if value.tzinfo is None:raise ValueError('UTC timestamp requires a timezone')
        return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

    def process_result_value(self,value,dialect):
        return datetime.fromisoformat(value.replace('Z','+00:00')) if value else None

def build_metadata(definitions):
    meta=sa.MetaData(naming_convention={'ix':'ix_%(table_name)s_%(column_0_name)s','uq':'uq_%(table_name)s_%(column_0_name)s','pk':'pk_%(table_name)s'})
    
    for name,spec in definitions.items():
        cols=[]
        for field,s in spec['columns'].items():
            typ={'uuid':sa.String(36),'integer':sa.BigInteger(),'quantity':Quantity(),'boolean':sa.Boolean(create_constraint=True),'datetime':UTCDateTime(),'date':sa.Date(),'string':sa.String(s['length']) if s['length'] else sa.Text()}[s['type']]
            kwargs={'nullable':s['nullable'],'primary_key':field=='id'}
            if field=='id':
                kwargs['default']=lambda:str(uuid.uuid4())
            elif 'default' in s:
                d=s['default']
                kwargs['default']=utcnow if d=='utcnow' else d
                if d!='utcnow':
                    if s['type'] == 'boolean' or isinstance(d, bool):
                        kwargs['server_default'] = sa.text('true' if d else 'false')
                    elif isinstance(d, (int, float, Decimal)):
                        kwargs['server_default'] = sa.text(str(d))
                    else:
                        kwargs['server_default'] = sa.text("'"+str(d).replace("'","''")+"'")
            cols.append(sa.Column(field,typ,**kwargs))
        
        table=sa.Table(name,meta,*cols)
        
        # Sử dụng uuid check đơn giản, tương thích cả 2
        table.append_constraint(sa.CheckConstraint("length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32", name=safe_name('ck', f'{name}_uuid')))
        
        for field,s in spec['columns'].items():
            if 'enum' in s:
                vals=','.join("'"+v+"'" for v in s['enum'])
                table.append_constraint(sa.CheckConstraint(f'{field} IN ({vals})',name=safe_name('ck', f'{name}_{field}_enum')))
            if s['type'] in ('integer','quantity') and field!='quantity_delta':
                table.append_constraint(sa.CheckConstraint(f'{field} >= 0',name=safe_name('ck', f'{name}_{field}_nonnegative')))
            if field in ('line_no','sequence_no'):
                table.append_constraint(sa.CheckConstraint(f'{field} > 0',name=safe_name('ck', f'{name}_{field}_positive')))
            if field=='username':
                table.append_constraint(sa.CheckConstraint('username = lower(trim(username))',name=safe_name('ck', 'username_normalized')))
            if field=='organization_id':
                table.append_constraint(sa.ForeignKeyConstraint([field],['organizations.id'],ondelete='RESTRICT', name=safe_name('fk', f'{name}_org')))
            elif 'references' in s:
                target=s['references'].split('.')[0]
                fk_name = safe_name('fk', f'{name}_{field}_{target}')
                table.append_constraint(sa.ForeignKeyConstraint(['organization_id',field],[target+'.organization_id',s['references']],ondelete='RESTRICT', name=fk_name))
                
        unique_fields=set()
        for i,fields in enumerate(spec.get('unique',[])):
            if tuple(fields) in unique_fields:continue
            unique_fields.add(tuple(fields))
            table.append_constraint(sa.UniqueConstraint(*fields,name=safe_name('uq', f'{name}_{i}')))
            
        # Xử lý EXTRA_CHECKS: loại bỏ các hàm typeof/glob cho Postgres
        extra_checks = {
         'employees':["terminated_on IS NULL OR hired_on IS NULL OR terminated_on >= hired_on"],
         'sales_orders':['total_amount = subtotal_amount - discount_amount + tax_amount','discount_amount <= subtotal_amount'],
         'sales_order_lines':['quantity > 0','discount_amount <= quantity * unit_price / 1000000'],
         'purchase_orders':['total_amount = subtotal_amount + tax_amount'],
         'purchase_order_lines':['quantity > 0','received_quantity <= quantity'],
         'supplier_bills':['total_amount = subtotal_amount + tax_amount','due_date IS NULL OR due_date >= bill_date'],
         'supplier_payments':['amount > 0'],
         'inventory_units':['remaining_quantity >= 0','initial_quantity >= 0'],
         'inventory_movements':["quantity_delta != 0"],
         'stock_transfers':['from_warehouse_id != to_warehouse_id'],
         'stock_transfer_lines':['quantity > 0'],
         'bills_of_materials':['output_quantity > 0','version_no > 0','effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from'],
         'bom_lines':['quantity > 0','scrap_rate BETWEEN 0 AND 10000'],
         'production_orders':['planned_quantity > 0','released_quantity <= planned_quantity','good_quantity + scrap_quantity <= released_quantity','planned_end_at IS NULL OR planned_start_at IS NULL OR planned_end_at >= planned_start_at'],
         'production_reports':['good_quantity + scrap_quantity > 0 OR downtime_minutes > 0'],
         'tasks':['due_at IS NULL OR start_at IS NULL OR due_at >= start_at'],
         'task_updates':['progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100'],
         'customer_invoices':['total_amount = subtotal_amount + tax_amount','due_date IS NULL OR due_date >= invoice_date'],
         'customer_invoice_lines':['quantity > 0'],
         'customer_receipts':['amount > 0'],
         'customer_payment_allocations':['amount > 0'],
         'kpi_targets':["period_end >= period_start", "(kpi_type = 'sales_revenue' AND target_amount IS NOT NULL AND target_value IS NULL) OR (kpi_type != 'sales_revenue' AND target_amount IS NULL AND target_value IS NOT NULL)"],
        }
        for i,check in enumerate(extra_checks.get(name,[])):
            table.append_constraint(sa.CheckConstraint(check,name=safe_name('ck', f'{name}_rule_{i}')))
            
        if name!='organizations':
            sa.Index(safe_name('ix', f'{name}_tenant'),table.c.organization_id)
        for field in spec['columns']:
            if field.endswith('_id') and field not in ('organization_id',):
                sa.Index(safe_name('ix', f'{name}_{field}'),table.c.organization_id,table.c[field])
        if 'partial_unique' in spec:
            p=spec['partial_unique']
            sa.Index(safe_name('uq', f'{name}_partial'),*[table.c[x] for x in p['fields']],unique=True)
            
    special_fks={
     'inventory_units':[(('location_id','warehouse_id'),'warehouse_locations',('id','warehouse_id')),(('lot_id','product_id'),'inventory_lots',('id','product_id'))],
     'inventory_movements':[(('inventory_unit_id','product_id'),'inventory_units',('id','product_id')),(('lot_id','product_id'),'inventory_lots',('id','product_id')),(('location_id','warehouse_id'),'warehouse_locations',('id','warehouse_id'))],
     'production_orders':[(('bom_id','product_id'),'bills_of_materials',('id','product_id'))],
     'production_order_operations':[(('machine_id','work_center_id'),'machines',('id','work_center_id'))],
     'shipments':[(('sales_order_id','customer_id'),'sales_orders',('id','customer_id'))],
     'customer_invoices':[(('sales_order_id','customer_id'),'sales_orders',('id','customer_id'))],
     'supplier_bills':[(('purchase_order_id','supplier_id'),'purchase_orders',('id','supplier_id'))],
    }
    for name,rels in special_fks.items():
        if name not in meta.tables:continue
        for i,(source,target,dest) in enumerate(rels):
            fields=['organization_id',*dest]
            if not any(isinstance(c,sa.UniqueConstraint) and list(c.columns.keys())==fields for c in meta.tables[target].constraints):
                meta.tables[target].append_constraint(sa.UniqueConstraint(*fields,name=safe_name('uq', f'{target}_paired_{name}_{i}')))
            meta.tables[name].append_constraint(sa.ForeignKeyConstraint(['organization_id',*source],[f'{target}.{f}' for f in fields],name=safe_name('fk', f'{name}_paired_{i}')))
    return meta

schema=json.loads(Path(__file__).with_name('schema.json').read_text(encoding='utf-8'))
metadata=build_metadata(schema)
mapper_registry=registry(metadata=metadata)
models={}
for name,table in metadata.tables.items():
    cls=type(''.join(p.title() for p in name.split('_')),(),{})
    mapper_registry.map_imperatively(cls,table)
    models[name]=cls