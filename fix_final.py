import sys
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import text

sys.path.append(r"D:\SUNNY_ERP\app")
from backend.app.database import make_engine

PG_URL = "postgresql://sunny_db_final_user:BHRklmBb7qhQbAcKoTxmlGmWiHv43ZLq@dpg-dbgbre7lk1mc73ba4q6g-a.singapore-postgres.render.com/sunny_db_final?sslmode=require"

def fix_db():
    config = Config(str(Path(r"D:\SUNNY_ERP\app\backend\alembic.ini").resolve()))
    engine = make_engine(PG_URL, foreign_keys=False)
    
    with engine.begin() as conn:
        config.attributes['connection'] = conn
        print("1. Đang đánh dấu baseline...")
        try:
            command.stamp(config, "0001_baseline")
        except Exception as e:
            print("Stamp skipped:", e)
        
        print("2. Đang tạo các bảng còn thiếu (auth_sessions...)...")
        try:
            command.upgrade(config, "head")
        except Exception as e:
            print(f"Lỗi Alembic (có thể do SQLite syntax): {e}")
            print("Đang dùng lệnh SQL thủ công để tạo bảng auth_sessions...")
            # Fallback if alembic fails due to sqlite specific syntax
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
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions(user_id);"))
    engine.dispose()
    print("=== ĐÃ XỬ LÝ XONG DATABASE ===")

fix_db()
