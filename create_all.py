import sqlalchemy as sa
from sqlalchemy import create_engine, text
import sys, uuid
from datetime import datetime, timezone
import argon2

sys.path.append(r"D:\SUNNY_ERP\app")
from backend.app.models import metadata as Base_metadata

PG_URL = "postgresql://sunny_db_final_user:BHRklmBb7qhQbAcKoTxmlGmWiHv43ZLq@dpg-dbgbre7lk1mc73ba4q6g-a.singapore-postgres.render.com/sunny_db_final?sslmode=require"

def create_everything():
    engine = create_engine(PG_URL)
    
    print("1. Đang xóa sạch toàn bộ Database cũ...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
    
    print("2. Đang tạo lại 44 bảng cơ bản...")
    Base_metadata.create_all(engine)

    print("3. Đang tạo các bảng mở rộng (auth_sessions, operation_keys...)")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                family_id VARCHAR(36),
                refresh_token_hash VARCHAR(255) NOT NULL,
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
                UNIQUE(organization_id, id),
                FOREIGN KEY(organization_id, payment_id) REFERENCES supplier_payments(organization_id, id),
                FOREIGN KEY(organization_id, bill_id) REFERENCES supplier_bills(organization_id, id),
                FOREIGN KEY(organization_id, created_by) REFERENCES app_users(organization_id, id)
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

    print("4. Đang tạo tài khoản Admin mới...")
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

    print("=== HOÀN TẤT TẤT CẢ! Tài khoản: admin / Mật khẩu: admin12345678 ===")

if __name__ == "__main__":
    create_everything()
