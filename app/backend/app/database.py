from contextlib import contextmanager
from pathlib import Path
import sqlite3
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

def make_engine(url,*,foreign_keys=True):
    engine=sa.create_engine(url,connect_args={'check_same_thread':False,'timeout':30},poolclass=NullPool)
    @sa.event.listens_for(engine,'connect')
    def configure(conn,record):
        conn.isolation_level=None
        conn.execute('PRAGMA foreign_keys='+('ON' if foreign_keys else 'OFF'))
        conn.execute('PRAGMA busy_timeout=30000')
        conn.execute('PRAGMA journal_mode=WAL')
    @sa.event.listens_for(engine,'begin')
    def begin(conn):conn.exec_driver_sql('BEGIN IMMEDIATE')
    return engine

@contextmanager
def transaction(engine):
    with Session(engine,expire_on_commit=False) as session:
        with session.begin():yield session

def backup_database(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_file() or source==destination or destination.exists():raise ValueError('Backup requires existing source and a new, different target')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or dst.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Backup integrity failure')
    return str(destination)

def verify_database(path):
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as c:
        return {'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_key_errors':c.execute('PRAGMA foreign_key_check').fetchall()}
