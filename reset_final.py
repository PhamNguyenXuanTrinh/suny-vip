import sqlalchemy as sa
from sqlalchemy import create_engine, text
import sys, uuid
from datetime import datetime, timezone
import argon2

sys.path.append(r"D:\SUNNY_ERP\app")
from backend.app.models import metadata as Base_metadata

# Đã dùng link External Database URL của bạn
PG_URL = "postgresql://sunny_db_final_user:BHRklmBb7qhQbAcKoTxmlGmWiHv43ZLq@dpg-dbgbre7lk1mc73ba4q6g-a.singapore-postgres.render.com/sunny_db_final?sslmode=require"

def hard_reset():
    engine = create_engine(PG_URL)
    
    print("1. Đang xóa sạch toàn bộ Database cũ...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
    
    print("2. Đang tạo lại cấu trúc 44 bảng chuẩn...")
    Base_metadata.create_all(engine)

    print("3. Đang tạo tài khoản Admin mới...")
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    org_id = str(uuid.uuid4())
    emp_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    hasher = argon2.PasswordHasher()
    pwd_hash = hasher.hash("admin12345678")

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO organizations (id, code, name, is_active, created_at, updated_at) VALUES (:id, 'SUNNY', 'Công Ty SUNNY', true, :now, :now)"), {"id": org_id, "now": now})
        conn.execute(text("INSERT INTO employees (id, organization_id, employee_code, full_name, status, created_at, updated_at) VALUES (:id, :org, 'ADMIN', 'Quản trị viên', 'active', :now, :now)"), {"id": emp_id, "org": org_id, "now": now})
        conn.execute(text("INSERT INTO app_users (id, organization_id, employee_id, username, password_hash, is_active, must_change_password, failed_login_count, created_at, updated_at) VALUES (:id, :org, :emp, 'admin', :pwd, true, false, 0, :now, :now)"), {"id": user_id, "org": org_id, "emp": emp_id, "pwd": pwd_hash, "now": now})
        
        role_id = str(uuid.uuid4())
        conn.execute(text("INSERT INTO roles (id, organization_id, code, name, is_system, is_active, created_at) VALUES (:id, :org, 'ADMIN', 'Quản trị viên', true, true, :now)"), {"id": role_id, "org": org_id, "now": now})
        conn.execute(text("INSERT INTO user_roles (id, organization_id, user_id, role_id, assigned_at) VALUES (:id, :org, :user, :role, :now)"), {"id": str(uuid.uuid4()), "org": org_id, "user": user_id, "role": role_id, "now": now})

    print("=== HOÀN TẤT! Tài khoản: admin / Mật khẩu: admin12345678 ===")

hard_reset()
