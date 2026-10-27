import sqlalchemy as sa
from sqlalchemy import create_engine, text

PG_URL = "postgresql://sunny_db_final_user:BHRklmBb7qhQbAcKoTxmlGmWiHv43ZLq@dpg-dbgbre7lk1mc73ba4q6g-a.singapore-postgres.render.com/sunny_db_final?sslmode=require"

def fix_sessions():
    engine = create_engine(PG_URL)
    with engine.begin() as conn:
        print("Đang xóa và tạo lại bảng auth_sessions với đúng tên cột...")
        conn.execute(text("DROP TABLE IF EXISTS auth_sessions CASCADE;"))
        conn.execute(text("""
            CREATE TABLE auth_sessions (
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
    print("=== ĐÃ SỬA XONG BẢNG auth_sessions! ===")

if __name__ == "__main__":
    fix_sessions()
