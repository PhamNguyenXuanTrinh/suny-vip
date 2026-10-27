import sqlite3
import pytest
from scripts.backup_database import backup,restore,verify

def test_backup_restore_preserves_rows(tmp_path):
    src=tmp_path/'source.db';out=tmp_path/'snapshot.db';dst=tmp_path/'restored.db'
    with sqlite3.connect(src) as c:
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('CREATE TABLE example(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL)')
        c.execute('INSERT INTO example VALUES(1,250)')
    assert backup(src,out)['integrity']=='ok'
    assert restore(out,dst)['integrity']=='ok'
    with sqlite3.connect(dst) as c:
        assert c.execute('SELECT amount FROM example WHERE id=1').fetchone()[0]==250
    with pytest.raises(FileExistsError):restore(out,dst)

def test_reject_corrupt_backup(tmp_path):
    bad=tmp_path/'bad.db';bad.write_bytes(b'not a database')
    with pytest.raises(sqlite3.DatabaseError):verify(bad)
