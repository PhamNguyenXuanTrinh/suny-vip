"""python -m backend.scripts.migrate_db --database runtime/database/sunny.sqlite3"""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from alembic import command
from alembic.config import Config
from backend.app.database import make_engine, backup_database, verify_database
import sqlalchemy as sa

def migrate(path_or_url, revision='head'):
    db_url = str(path_or_url)
    
    is_postgres = db_url.startswith('postgresql://') or db_url.startswith('postgres://')
    
    if is_postgres:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
            
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        engine = make_engine(db_url, foreign_keys=False)
        
        # KIỂM TRA: Nếu đã có bảng organizations (do reset_final.py tạo) thì bỏ qua Alembic
        inspector = sa.inspect(engine)
        if 'organizations' in inspector.get_table_names():
            print("PostgreSQL Database đã được khởi tạo. Bỏ qua Alembic.")
            engine.dispose()
            return {'database': db_url, 'status': 'skipped (already initialized)'}
            
        backup = None
        try:
            with engine.begin() as conn:
                config.attributes['connection'] = conn
                command.upgrade(config, revision)
        finally:
            engine.dispose()
        return {'database': db_url, 'backup': backup, 'status': 'migrated'}
        
    else:
        # Code cũ cho SQLite (Local)
        path = Path(db_url.replace('sqlite:///', ''))
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        backup = None
        if path.exists() and path.stat().st_size:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = backup_database(path, path.parent / 'backups' / (path.name + '.' + stamp + '.bak'))
            
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        engine = make_engine(f'sqlite:///{path}', foreign_keys=False)
        try:
            with engine.begin() as conn:
                config.attributes['connection'] = conn
                command.upgrade(config, revision)
                if conn.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
                    raise RuntimeError('Invalid references after migration; transaction rolled back')
        finally:
            engine.dispose()
        return {'database': str(path), 'backup': backup, **verify_database(path)}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--database', required=True)
    print(migrate(p.parse_args().database))