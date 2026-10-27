import sqlalchemy as sa
from sqlalchemy import create_engine, text

PG_URL = "postgresql://sunny_db_final_user:BHRklmBb7qhQbAcKoTxmlGmWiHv43ZLq@dpg-dbgbre7lk1mc73ba4q6g-a.singapore-postgres.render.com/sunny_db_final?sslmode=require"

def fix_missing_tables():
    engine = create_engine(PG_URL)
    with engine.begin() as conn:
        print("Đang tạo bảng còn thiếu: payment_allocation_events...")
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
        
        print("Đang tạo bảng còn thiếu: supplier_payment_allocations...")
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
        
    print("=== ĐÃ SỬA XONG! Bảng đã được thêm vào Database ===")

if __name__ == "__main__":
    fix_missing_tables()
