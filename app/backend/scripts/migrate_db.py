"""python -m backend.scripts.migrate_db --database runtime/database/sunny.sqlite3"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
from alembic import command
from alembic.config import Config
from backend.app.database import make_engine,backup_database,verify_database

def migrate(path,revision='head'):
    path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    backup=None
    if path.exists() and path.stat().st_size:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=backup_database(path,path.parent/'backups'/(path.name+'.'+stamp+'.bak'))
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    engine=make_engine('sqlite:///'+str(path),foreign_keys=False)
    try:
        with engine.begin() as conn:
            config.attributes['connection']=conn
            command.upgrade(config,revision)
            if conn.exec_driver_sql('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Invalid references after migration; transaction rolled back')
    finally:engine.dispose()
    return {'database':str(path),'backup':backup,**verify_database(path)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True)
    print(migrate(p.parse_args().database))
