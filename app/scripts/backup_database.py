"""Offline/online-consistent SQLite backup and verified restore for phase 01.

Usage:
 python scripts/backup_database.py backup --output /safe/backup.sqlite3
 python scripts/backup_database.py verify --file /safe/backup.sqlite3
 python scripts/backup_database.py restore --file /safe/backup.sqlite3 --output /new/sunny.sqlite3
Never restore over a running server's active database.
"""
import argparse
import hashlib
import sqlite3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.db import DB

def verify(path):
    path=Path(path)
    if not path.is_file(): raise ValueError('Không tìm thấy tệp sao lưu')
    with sqlite3.connect(f'file:{path.resolve()}?mode=ro',uri=True) as c:
        result=c.execute('PRAGMA integrity_check').fetchone()[0]
        fk=c.execute('PRAGMA foreign_key_check').fetchall()
    if result!='ok' or fk:raise ValueError(f'Cơ sở dữ liệu không hợp lệ: {result}; FK={len(fk)}')
    return {'integrity':'ok','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}

def backup(source,dest):
    source,dest=Path(source),Path(dest)
    if not source.is_file():raise ValueError('Chưa có cơ sở dữ liệu nguồn')
    if source.resolve()==dest.resolve():raise ValueError('Không ghi đè dữ liệu đang chạy')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise FileExistsError('Tệp đích đã tồn tại, không ghi đè')
    try:
        with sqlite3.connect(f'file:{source.resolve()}?mode=ro',uri=True) as src, sqlite3.connect(dest) as dst:
            src.backup(dst)
        return verify(dest)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

def restore(source,dest):
    verify(source)
    return backup(source,dest)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','verify','restore']);p.add_argument('--file');p.add_argument('--output');p.add_argument('--source');args=p.parse_args()
    if args.action=='verify':result=verify(args.file)
    elif args.action=='backup':result=backup(args.source or DB,args.output)
    else:result=restore(args.file,args.output)
    print(result)
