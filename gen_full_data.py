import sys
sys.path.append(r"D:\SUNNY_ERP\app")
from backend.app.models import models, metadata as Base_metadata
from backend.app.database import make_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone, timedelta
import random
import argon2

PG_URL = "postgresql://sunny_db_final_user:BHRklmBb7qhQbAcKoTxmlGmWiHv43ZLq@dpg-dbgbre7lk1mc73ba4q6g-a.singapore-postgres.render.com/sunny_db_final?sslmode=require"

def safe_add(session, model_name, data):
    model = models[model_name]
    columns = [c.name for c in model.__table__.columns]
    filtered_data = {k: v for k, v in data.items() if k in columns}
    session.add(model(**filtered_data))

def generate_full_data():
    engine = make_engine(PG_URL)
    
    print("1. Đang tạo lại toàn bộ Database (Xóa sạch)...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
    
    Base_metadata.create_all(engine)
    
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36) NOT NULL, user_id VARCHAR(36) NOT NULL,
                family_id VARCHAR(36), refresh_hash VARCHAR(255) NOT NULL, created_at VARCHAR(32) NOT NULL,
                expires_at VARCHAR(32) NOT NULL, revoked_at VARCHAR(32), replaced_by_id VARCHAR(36), user_agent TEXT, ip_address VARCHAR(45)
            );
            CREATE TABLE IF NOT EXISTS operation_keys (
                id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36) NOT NULL, user_id VARCHAR(36) NOT NULL,
                key VARCHAR(255) NOT NULL, request_hash VARCHAR(255) NOT NULL, response_json TEXT, created_at VARCHAR(32) NOT NULL, UNIQUE (organization_id, key)
            );
        """))

    print("2. Đang tạo dữ liệu nền tảng...")
    org_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_str = now.isoformat().replace('+00:00', 'Z')
    
    hasher = argon2.PasswordHasher()
    pwd_hash = hasher.hash("admin12345678")

    with Session(engine) as session:
        # Cấp 1: Tổ chức & Roles
        safe_add(session, 'organizations', {'id': org_id, 'code': 'SUNNY', 'name': 'Tập Đoàn SUNNY', 'is_active': True, 'created_at': now_str, 'updated_at': now_str})
        roles = {'ADMIN': 'Quản trị viên', 'SALES': 'Kinh doanh', 'KHO': 'Thủ kho', 'SX': 'Sản xuất', 'KT': 'Kế toán'}
        role_ids = {}
        for code, name in roles.items():
            rid = str(uuid.uuid4())
            role_ids[code] = rid
            safe_add(session, 'roles', {'id': rid, 'organization_id': org_id, 'code': code, 'name': name, 'is_system': True, 'is_active': True, 'created_at': now_str})
        session.commit()

        # Cấp 2: Nhà máy & Kho
        site_id = str(uuid.uuid4())
        safe_add(session, 'sites', {'id': site_id, 'organization_id': org_id, 'code': 'NM01', 'name': 'Nhà máy Bình Dương', 'is_active': True, 'created_at': now_str, 'updated_at': now_str})
        wh_nvl_id, wh_tp_id = str(uuid.uuid4()), str(uuid.uuid4())
        safe_add(session, 'warehouses', {'id': wh_nvl_id, 'organization_id': org_id, 'site_id': site_id, 'code': 'KHO_NVL', 'name': 'Kho Nguyên Vật Liệu', 'is_active': True, 'created_at': now_str, 'updated_at': now_str})
        safe_add(session, 'warehouses', {'id': wh_tp_id, 'organization_id': org_id, 'site_id': site_id, 'code': 'KHO_TP', 'name': 'Kho Thành Phẩm', 'is_active': True, 'created_at': now_str, 'updated_at': now_str})
        session.commit()

        # Cấp 3: Phòng ban
        depts = {'KD': 'Phòng Kinh Doanh', 'SX': 'Xưởng Sản Xuất', 'KHO': 'Phòng Kho Vận', 'KT': 'Phòng Kế Toán'}
        dept_ids = {}
        for code, name in depts.items():
            did = str(uuid.uuid4())
            dept_ids[code] = did
            safe_add(session, 'departments', {'id': did, 'organization_id': org_id, 'code': code, 'name': name, 'is_active': True, 'created_at': now_str, 'updated_at': now_str})
        session.commit()

        # Cấp 4: Nhân viên
        users_info = [('ADMIN', 'Quản trị viên', 'ADMIN', None), ('SALES1', 'Nguyễn Văn Sale', 'SALES', 'KD'), ('KHO1', 'Trần Thị Kho', 'KHO', 'KHO'), ('SX1', 'Lê Văn Công Nhân', 'SX', 'SX'), ('KT1', 'Phạm Thị Kế Toán', 'KT', 'KT')]
        emp_ids = {}
        for code, name, _, dept_code in users_info:
            eid = str(uuid.uuid4())
            emp_ids[code] = eid
            safe_add(session, 'employees', {
                'id': eid, 'organization_id': org_id, 'site_id': site_id, 'department_id': dept_ids.get(dept_code),
                'employee_code': code, 'full_name': name, 'status': 'active', 'created_at': now_str, 'updated_at': now_str
            })
        session.commit() 

        # Cấp 5: Tài khoản User
        admin_user_id = None
        for code, name, role_code, _ in users_info:
            eid = emp_ids[code]
            uid = str(uuid.uuid4())
            safe_add(session, 'app_users', {
                'id': uid, 'organization_id': org_id, 'employee_id': eid, 'username': code.lower(),
                'password_hash': pwd_hash, 'is_active': True, 'must_change_password': False, 'failed_login_count': 0, 'created_at': now_str, 'updated_at': now_str
            })
            safe_add(session, 'user_roles', {'id': str(uuid.uuid4()), 'organization_id': org_id, 'user_id': uid, 'role_id': role_ids[role_code], 'assigned_at': now_str})
            if role_code == 'ADMIN': admin_user_id = uid
        session.commit()

        # Cấp 6: Sản phẩm, NCC, Khách hàng
        products = [('NVL01', 'Vải Cotton Trắng', 'raw_material', 'Mét'), ('NVL02', 'Chỉ May', 'raw_material', 'Cuộn'), ('TP01', 'Áo Thun Nam', 'finished_good', 'Cái'), ('TP02', 'Áo Thun Nữ', 'finished_good', 'Cái')]
        prod_ids = {}
        for sku, name, ptype, uom in products:
            pid = str(uuid.uuid4())
            prod_ids[sku] = pid
            safe_add(session, 'products', {
                'id': pid, 'organization_id': org_id, 'sku': sku, 'name': name, 'product_type': ptype,
                'base_uom': uom, 'tracking_method': 'none', 'is_purchasable': True, 'is_sellable': True,
                'is_manufactured': (ptype == 'finished_good'), 'is_active': True, 'created_at': now_str, 'updated_at': now_str
            })
        sup_ids = {}
        for code, name in [('NCC01', 'Công ty Vải Sợi X'), ('NCC02', 'Công ty Phụ Liệu Y')]:
            sid = str(uuid.uuid4())
            sup_ids[code] = sid
            safe_add(session, 'suppliers', {'id': sid, 'organization_id': org_id, 'supplier_code': code, 'name': name, 'status': 'active', 'created_at': now_str, 'updated_at': now_str})
        cust_ids = {}
        for code, name in [('KH01', 'Cửa hàng Thời trang A'), ('KH02', 'Đại lý B'), ('KH03', 'Công ty May Mặc C')]:
            cid = str(uuid.uuid4())
            cust_ids[code] = cid
            safe_add(session, 'customers', {'id': cid, 'organization_id': org_id, 'customer_code': code, 'name': name, 'status': 'active', 'created_at': now_str, 'updated_at': now_str})
        session.commit()

        print("3. Đang tạo dữ liệu Mua hàng & Nhập kho...")
        po_id = str(uuid.uuid4())
        safe_add(session, 'purchase_orders', {
            'id': po_id, 'organization_id': org_id, 'po_code': 'PO-001', 'supplier_id': sup_ids['NCC01'],
            'ordered_at': (now - timedelta(days=80)).isoformat().replace('+00:00', 'Z'), 'status': 'received',
            'subtotal_amount': 52000000, 'tax_amount': 0, 'total_amount': 52000000, 'created_by': admin_user_id,
            'created_at': now_str, 'updated_at': now_str
        })
        session.commit() 

        safe_add(session, 'purchase_order_lines', {'id': str(uuid.uuid4()), 'organization_id': org_id, 'purchase_order_id': po_id, 'line_no': 1, 'product_id': prod_ids['NVL01'], 'quantity': 1000, 'uom': 'Mét', 'unit_price': 50000})
        safe_add(session, 'purchase_order_lines', {'id': str(uuid.uuid4()), 'organization_id': org_id, 'purchase_order_id': po_id, 'line_no': 2, 'product_id': prod_ids['NVL02'], 'quantity': 200, 'uom': 'Cuộn', 'unit_price': 10000})
        session.commit() 

        for i, (sku, qty) in enumerate([('NVL01', 1000), ('NVL02', 200)]):
            safe_add(session, 'inventory_movements', {
                'id': str(uuid.uuid4()), 'organization_id': org_id, 'movement_code': f'IN-{i+1:03d}', 'movement_type': 'receipt',
                'product_id': prod_ids[sku], 'warehouse_id': wh_nvl_id, 'quantity_delta': qty, 'unit_cost': 50000,
                'total_value': qty*50000, 'occurred_at': now_str, 'reference_type': 'purchase_order', 'reference_id': po_id,
                'idempotency_key': f'IN-{i+1}', 'actor_user_id': admin_user_id, 'created_at': now_str
            })
        session.commit()

        print("4. Đang tạo dữ liệu Sản xuất...")
        # TẠO BOM TRƯỚC
        bom_id = str(uuid.uuid4())
        safe_add(session, 'bills_of_materials', {
            'id': bom_id, 'organization_id': org_id, 'bom_code': 'BOM-TP01', 'product_id': prod_ids['TP01'],
            'version_no': 1, 'output_quantity': 1, 'status': 'active', 'created_at': now_str, 'updated_at': now_str
        })
        session.commit()

        # Tạo Lệnh sản xuất (Dùng bom_id vừa tạo)
        mo_id = str(uuid.uuid4())
        safe_add(session, 'production_orders', {
            'id': mo_id, 'organization_id': org_id, 'production_order_code': 'LSX-001', 'product_id': prod_ids['TP01'],
            'bom_id': bom_id, 'planned_quantity': 500, 'released_quantity': 500, 'good_quantity': 500, 'scrap_quantity': 0,
            'status': 'completed', 'created_by': admin_user_id, 'created_at': now_str, 'updated_at': now_str
        })
        session.commit()
        
        safe_add(session, 'inventory_movements', {'id': str(uuid.uuid4()), 'organization_id': org_id, 'movement_code': 'OUT-001', 'movement_type': 'production_consume', 'product_id': prod_ids['NVL01'], 'warehouse_id': wh_nvl_id, 'quantity_delta': -750, 'unit_cost': 50000, 'total_value': 37500000, 'occurred_at': now_str, 'reference_type': 'production_order', 'reference_id': mo_id, 'idempotency_key': 'OUT-001', 'actor_user_id': admin_user_id, 'created_at': now_str})
        safe_add(session, 'inventory_movements', {'id': str(uuid.uuid4()), 'organization_id': org_id, 'movement_code': 'IN-003', 'movement_type': 'production_output', 'product_id': prod_ids['TP01'], 'warehouse_id': wh_tp_id, 'quantity_delta': 500, 'unit_cost': 75000, 'total_value': 37500000, 'occurred_at': now_str, 'reference_type': 'production_order', 'reference_id': mo_id, 'idempotency_key': 'IN-003', 'actor_user_id': admin_user_id, 'created_at': now_str})
        session.commit()

        print("5. Đang tạo dữ liệu Bán hàng & Kế toán...")
        cust_keys = list(cust_ids.keys())
        order_ids = []
        for i in range(1, 51):
            order_id = str(uuid.uuid4())
            order_ids.append(order_id)
            days_ago = random.randint(0, 60)
            order_date = (now - timedelta(days=days_ago)).isoformat().replace('+00:00', 'Z')
            qty = random.randint(10, 50)
            price = 150000
            total = qty * price
            cid = cust_ids[random.choice(cust_keys)]

            safe_add(session, 'sales_orders', {
                'id': order_id, 'organization_id': org_id, 'order_code': f'SO-{i:04d}', 'customer_id': cid,
                'ordered_at': order_date, 'status': 'completed', 'subtotal_amount': total, 'discount_amount': 0,
                'tax_amount': 0, 'total_amount': total, 'created_by': admin_user_id, 'created_at': order_date, 'updated_at': order_date
            })
        session.commit()

        for i in range(1, 51):
            order_id = order_ids[i-1]
            days_ago = random.randint(0, 60)
            order_date = (now - timedelta(days=days_ago)).isoformat().replace('+00:00', 'Z')
            qty = random.randint(10, 50)
            price = 150000
            total = qty * price

            safe_add(session, 'sales_order_lines', {
                'id': str(uuid.uuid4()), 'organization_id': org_id, 'order_id': order_id, 'line_no': 1,
                'product_id': prod_ids['TP01'], 'quantity': qty, 'uom': 'Cái', 'unit_price': price,
                'discount_amount': 0, 'tax_rate': 0, 'line_total': total
            })
        session.commit()

        for i in range(1, 31):
            order_id = order_ids[i-1]
            order_data = session.execute(text("SELECT customer_id, ordered_at, total_amount FROM sales_orders WHERE id = :id"), {"id": order_id}).fetchone()
            if not order_data: continue
            cid, order_date, total = order_data

            inv_id = str(uuid.uuid4())
            safe_add(session, 'customer_invoices', {
                'id': inv_id, 'organization_id': org_id, 'invoice_no': f'INV-{i:04d}', 'customer_id': cid,
                'sales_order_id': order_id, 'invoice_date': order_date, 'currency': 'VND',
                'subtotal_amount': total, 'tax_amount': 0, 'total_amount': total, 'status': 'paid',
                'created_at': order_date, 'updated_at': order_date
            })
            rec_id = str(uuid.uuid4())
            safe_add(session, 'customer_receipts', {
                'id': rec_id, 'organization_id': org_id, 'receipt_code': f'REC-{i:04d}', 'customer_id': cid,
                'received_at': order_date, 'amount': total, 'currency': 'VND', 'payment_method': 'bank_transfer',
                'status': 'verified', 'created_at': order_date
            })
            session.commit()

            safe_add(session, 'customer_payment_allocations', {
                'id': str(uuid.uuid4()), 'organization_id': org_id, 'receipt_id': rec_id, 
                'invoice_id': inv_id, 'amount': total, 'created_at': order_date, 'created_by': admin_user_id
            })
            session.commit()

        print("6. Đang tạo Công việc...")
        for i in range(1, 15):
            safe_add(session, 'tasks', {
                'id': str(uuid.uuid4()), 'organization_id': org_id, 'task_code': f'TASK-{i:03d}', 'title': f'Công việc số {i}',
                'task_type': 'general', 'priority': 'normal', 'status': random.choice(['open', 'in_progress', 'completed']),
                'created_by': admin_user_id, 'start_at': now_str, 'due_at': (now + timedelta(days=5)).isoformat().replace('+00:00', 'Z'),
                'created_at': now_str, 'updated_at': now_str
            })
        session.commit()

    print("=== THÀNH CÔNG RỰC RỠ! Đã tạo toàn bộ dữ liệu công ty ===")

if __name__ == "__main__":
    generate_full_data()
