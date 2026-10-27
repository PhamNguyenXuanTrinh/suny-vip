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

def generate_data():
    engine = make_engine(PG_URL)
    
    print("1. Đang tạo lại toàn bộ Database (Xóa sạch)...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
    
    print("2. Tạo 44 bảng cơ bản...")
    Base_metadata.create_all(engine)
    
    print("3. Tạo các bảng mở rộng (auth_sessions, v.v.)...")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                family_id VARCHAR(36),
                refresh_hash VARCHAR(255) NOT NULL,
                created_at VARCHAR(32) NOT NULL,
                expires_at VARCHAR(32) NOT NULL,
                revoked_at VARCHAR(32),
                replaced_by_id VARCHAR(36),
                user_agent TEXT,
                ip_address VARCHAR(45)
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS operation_keys (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                key VARCHAR(255) NOT NULL,
                request_hash VARCHAR(255) NOT NULL,
                response_json TEXT,
                created_at VARCHAR(32) NOT NULL,
                UNIQUE (organization_id, key)
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_conversations (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                title TEXT,
                created_at VARCHAR(32) NOT NULL,
                updated_at VARCHAR(32) NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_messages (
                id VARCHAR(36) PRIMARY KEY,
                conversation_id VARCHAR(36) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT,
                status VARCHAR(20) NOT NULL,
                tokens_in BIGINT DEFAULT 0,
                tokens_out BIGINT DEFAULT 0,
                created_at VARCHAR(32) NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS production_report_corrections (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                report_id VARCHAR(36) NOT NULL,
                old_good BIGINT,
                new_good BIGINT,
                old_scrap BIGINT,
                new_scrap BIGINT,
                reason TEXT NOT NULL,
                created_at VARCHAR(32) NOT NULL,
                created_by VARCHAR(36) NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS supplier_payment_allocations (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                payment_id VARCHAR(36) NOT NULL,
                bill_id VARCHAR(36) NOT NULL,
                amount BIGINT NOT NULL CHECK (amount > 0),
                created_at VARCHAR(32) NOT NULL,
                created_by VARCHAR(36) NOT NULL,
                UNIQUE(payment_id, bill_id),
                UNIQUE(organization_id, id)
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS payment_allocation_events (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                allocation_id VARCHAR(36) NOT NULL,
                amount BIGINT NOT NULL CHECK (amount > 0),
                created_at VARCHAR(32) NOT NULL,
                actor_id VARCHAR(36)
            );
        """))

    print("4. Tạo tài khoản Admin mới...")
    now = datetime.now(timezone.utc)
    now_str = now.isoformat().replace('+00:00', 'Z')
    
    org_id = str(uuid.uuid4())
    emp_id_admin = str(uuid.uuid4())
    user_id_admin = str(uuid.uuid4())
    
    hasher = argon2.PasswordHasher()
    pwd_hash = hasher.hash("admin12345678")

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO organizations (id, code, name, is_active, created_at, updated_at) VALUES (:id, 'SUNNY', 'Công Ty SUNNY', true, :now, :now)"), {"id": org_id, "now": now_str})
        conn.execute(text("INSERT INTO employees (id, organization_id, employee_code, full_name, status, created_at, updated_at) VALUES (:id, :org, 'ADMIN', 'Quản trị viên', 'active', :now, :now)"), {"id": emp_id_admin, "org": org_id, "now": now_str})
        conn.execute(text("INSERT INTO app_users (id, organization_id, employee_id, username, password_hash, is_active, must_change_password, failed_login_count, created_at, updated_at) VALUES (:id, :org, :emp, 'admin', :pwd, true, false, 0, :now, :now)"), {"id": user_id_admin, "org": org_id, "emp": emp_id_admin, "pwd": pwd_hash, "now": now_str})
        
        role_id = str(uuid.uuid4())
        conn.execute(text("INSERT INTO roles (id, organization_id, code, name, is_system, is_active, created_at) VALUES (:id, :org, 'ADMIN', 'Quản trị viên', true, true, :now)"), {"id": role_id, "org": org_id, "now": now_str})
        conn.execute(text("INSERT INTO user_roles (id, organization_id, user_id, role_id, assigned_at) VALUES (:id, :org, :user, :role, :now)"), {"id": str(uuid.uuid4()), "org": org_id, "user": user_id_admin, "role": role_id, "now": now_str})

    print("5. Đang tạo dữ liệu mẫu...")
    with Session(engine) as session:
        site_id = str(uuid.uuid4())
        safe_add(session, 'sites', {
            'id': site_id, 'organization_id': org_id, 'code': 'NM01', 'name': 'Nhà máy sản xuất số 1', 
            'address': 'KCN Tân Bình', 'is_active': True, 'created_at': now_str, 'updated_at': now_str
        })
        
        wh_id = str(uuid.uuid4())
        safe_add(session, 'warehouses', {
            'id': wh_id, 'organization_id': org_id, 'site_id': site_id, 'code': 'KHO_TP', 
            'name': 'Kho Thành phẩm', 'is_active': True, 'created_at': now_str, 'updated_at': now_str
        })
        
        dept_id = str(uuid.uuid4())
        safe_add(session, 'departments', {
            'id': dept_id, 'organization_id': org_id, 'code': 'KD', 'name': 'Phòng Kinh Doanh', 
            'is_active': True, 'created_at': now_str, 'updated_at': now_str
        })
        session.commit()

        emp_id = str(uuid.uuid4())
        safe_add(session, 'employees', {
            'id': emp_id, 'organization_id': org_id, 'site_id': site_id, 'department_id': dept_id, 
            'employee_code': 'NV01', 'full_name': 'Nguyễn Văn Sale', 'status': 'active', 
            'created_at': now_str, 'updated_at': now_str
        })

        cust_id = str(uuid.uuid4())
        safe_add(session, 'customers', {
            'id': cust_id, 'organization_id': org_id, 'customer_code': 'KH01', 
            'name': 'Công ty Thương mại ABC', 'phone': '0901234567', 'email': 'abc@gmail.com', 
            'billing_address': 'Quận 1, TP.HCM', 'status': 'active', 
            'created_at': now_str, 'updated_at': now_str
        })

        sup_id = str(uuid.uuid4())
        safe_add(session, 'suppliers', {
            'id': sup_id, 'organization_id': org_id, 'supplier_code': 'NCC01', 
            'name': 'Nhà máy Vật liệu XYZ', 'phone': '0912345678', 'email': 'xyz@gmail.com', 
            'address': 'Bình Dương', 'status': 'active', 
            'created_at': now_str, 'updated_at': now_str
        })

        prod_id = str(uuid.uuid4())
        safe_add(session, 'products', {
            'id': prod_id, 'organization_id': org_id, 'sku': 'SP01', 'name': 'Áo Thun Thể Thao', 
            'product_type': 'finished_good', 'base_uom': 'Cái', 'tracking_method': 'none',
            'is_purchasable': True, 'is_sellable': True, 'is_manufactured': True, 'is_active': True, 
            'created_at': now_str, 'updated_at': now_str
        })
        session.commit()

        print("6. Đang tạo 30 Đơn bán hàng (Lưu trước)...")
        order_ids = []
        for i in range(1, 31):
            order_id = str(uuid.uuid4())
            order_ids.append(order_id)
            days_ago = random.randint(0, 60)
            order_date = (now - timedelta(days=days_ago)).isoformat().replace('+00:00', 'Z')
            
            qty = random.randint(10, 100)
            price = 150000
            total = qty * price

            safe_add(session, 'sales_orders', {
                'id': order_id, 'organization_id': org_id, 'order_code': f"SO-{i:04d}", 
                'customer_id': cust_id, 'ordered_at': order_date, 'status': 'confirmed', 
                'subtotal_amount': total, 'discount_amount': 0, 'tax_amount': 0, 'total_amount': total, 
                'created_by': user_id_admin, 'created_at': order_date, 'updated_at': order_date
            })
        
        session.commit()

        print("7. Đang tạo chi tiết Đơn hàng (Lưu sau)...")
        for i, order_id in enumerate(order_ids):
            qty = random.randint(10, 100)
            price = 150000
            total = qty * price
            safe_add(session, 'sales_order_lines', {
                'id': str(uuid.uuid4()), 'organization_id': org_id, 'order_id': order_id, 
                'line_no': 1, 'product_id': prod_id, 'quantity': qty, 'uom': 'Cái', 
                'unit_price': price, 'discount_amount': 0, 'tax_rate': 0, 'line_total': total
            })
        
        session.commit()

    print("=== THÀNH CÔNG RỰC RỠ! Tài khoản: admin / Mật khẩu: admin12345678 ===")

if __name__ == "__main__":
    generate_data()
