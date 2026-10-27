"""Private, consistent whole-server backups for the local machine operator.

These functions are intentionally not exposed to organization administrators in
the ERP API: a server backup contains every organization on that machine.
"""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile

FORMAT = 'sunny-server-backup-v1'
MAX_UNPACKED = 4_000_000_000
SAFE_UPLOAD = re.compile(r'[a-f0-9]{32}\.(?:pdf|jpg|png)\Z')
SAFE_SETTINGS = {'SUNNY_ALLOWED_ORIGINS', 'SUNNY_OPENAI_MODEL',
                 'SUNNY_ALERT_INTERVAL_SECONDS', 'SUNNY_RECEIPT_SPIKE_THRESHOLDS',
                 'SUNNY_BUSINESS_TIMEZONE', 'SUNNY_MAX_SESSIONS'}


def read_config(path):
    values = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        key, sep, value = line.partition('=')
        if sep and re.fullmatch(r'[A-Z][A-Z0-9_]*', key.strip()):
            values[key.strip()] = value.strip()
    return values


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix='.sunny-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def write_config(path, values):
    if any(not re.fullmatch(r'[A-Z][A-Z0-9_]*', k) or '\n' in str(v) or '\r' in str(v)
           for k, v in values.items()):
        raise ValueError('Cấu hình có ký tự không hợp lệ')
    private_write(path, ('\n'.join(k+'='+str(v) for k, v in values.items())+'\n').encode())


def verify_sqlite(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)) as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        foreign = conn.execute('PRAGMA foreign_key_check').fetchall()
        if integrity != 'ok' or foreign:
            raise ValueError('Cơ sở dữ liệu không đạt kiểm tra toàn vẹn')
        conn.execute('SELECT id FROM app_users LIMIT 1').fetchall()
    return {'integrity': 'ok', 'foreign_key_errors': []}


def file_hash(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def create_backup(config_path, backup_dir, automatic=False):
    values = read_config(config_path)
    database = Path(values['SUNNY_ERP_DB']).resolve()
    uploads = Path(values['SUNNY_UPLOAD_DIR']).resolve()
    if not database.is_file():
        raise ValueError('Chưa có cơ sở dữ liệu để sao lưu')
    destination = Path(backup_dir)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = destination / (('auto-' if automatic else 'sunny-')+stamp+'.sunnybackup')
    with tempfile.TemporaryDirectory(prefix='.backup-', dir=destination) as temp:
        temp = Path(temp)
        snapshot = temp/'database.sqlite3'
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as src:
            with closing(sqlite3.connect(snapshot)) as dst:
                src.backup(dst)
        verify_sqlite(snapshot)
        with closing(sqlite3.connect(snapshot)) as conn:
            documents = conn.execute('SELECT storage_key, sha256, byte_size FROM documents').fetchall()
        settings = {k: v for k, v in values.items() if k in SAFE_SETTINGS}
        settings_bytes = json.dumps(settings, ensure_ascii=False).encode()
        if snapshot.stat().st_size+sum(r[2] for r in documents)+len(settings_bytes)>MAX_UNPACKED:
            raise ValueError('Dữ liệu sao lưu vượt giới hạn 4 GB; cần phương án lưu trữ máy chủ lớn hơn')
        manifest = {'format': FORMAT, 'created_at': datetime.now(timezone.utc).isoformat(),
                    'all_organizations': True, 'api_keys_included': False,
                    'login_password_hashes_included': True, 'files': {}}
        archive = temp/'complete.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(snapshot, 'database.sqlite3')
            manifest['files']['database.sqlite3'] = file_hash(snapshot)
            z.writestr('settings.json', settings_bytes)
            manifest['files']['settings.json'] = hashlib.sha256(settings_bytes).hexdigest()
            for key, expected, size in documents:
                if not SAFE_UPLOAD.fullmatch(key):
                    raise ValueError('Tên tệp chứng từ không hợp lệ')
                file = uploads/key
                if file.is_symlink() or not file.is_file():
                    raise ValueError('Thiếu tệp chứng từ; bản sao lưu chưa được tạo')
                digest = file_hash(file)
                if digest != expected or file.stat().st_size != size:
                    raise ValueError('Tệp chứng từ không khớp dữ liệu; bản sao lưu chưa được tạo')
                entry = 'uploads/'+key
                z.write(file, entry)
                manifest['files'][entry] = digest
            z.writestr('backup.json', json.dumps(manifest, ensure_ascii=False))
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist())>MAX_UNPACKED:
                raise ValueError('Dữ liệu sao lưu vượt giới hạn 4 GB')
            if z.testzip() is not None:
                raise ValueError('Không xác minh được bản sao lưu')
        archive.chmod(0o600)
        os.replace(archive, target)
    return {'name': target.name, 'bytes': target.stat().st_size,
            'documents': len(documents), 'created_at': manifest['created_at']}


def restore_backup(archive_path, data_dir, active_config):
    """Restore into a new profile, verify/migrate, then atomically switch config.

    The caller must stop the ERP server first. Existing profiles are retained;
    this function never deletes or overwrites the currently active database.
    """
    data_dir = Path(data_dir).resolve()
    active_config = Path(active_config).resolve()
    target = data_dir/'profiles'/('restore-'+uuid.uuid4().hex)
    target.mkdir(parents=True, mode=0o700)
    switched = False
    try:
        with zipfile.ZipFile(archive_path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or len(names) > 100_000:
                raise ValueError('Bản sao lưu có mục trùng hoặc quá nhiều tệp')
            unpacked=sum(i.file_size for i in infos)
            if shutil.disk_usage(target).free<unpacked*2+64_000_000:
                raise ValueError('Không đủ dung lượng trống để phục hồi và giữ bản sao an toàn')
            if unpacked > MAX_UNPACKED:
                raise ValueError('Bản sao lưu vượt giới hạn 4 GB')
            if not {'backup.json', 'database.sqlite3', 'settings.json'} <= set(names):
                raise ValueError('Tệp không phải bản sao lưu SUNNY đầy đủ')
            if z.getinfo('backup.json').file_size > 16_000_000:
                raise ValueError('Danh mục sao lưu quá lớn')
            manifest = json.loads(z.read('backup.json'))
            if manifest.get('format') != FORMAT or not isinstance(manifest.get('files'), dict):
                raise ValueError('Định dạng sao lưu không được hỗ trợ')
            if set(names) != set(manifest['files']) | {'backup.json'}:
                raise ValueError('Danh mục sao lưu không khớp các tệp')
            for info in infos:
                name = info.filename
                if name == 'backup.json':
                    continue
                if name not in ('database.sqlite3', 'settings.json') and not (
                    name.startswith('uploads/') and SAFE_UPLOAD.fullmatch(name[8:])):
                    raise ValueError('Đường dẫn trong bản sao lưu không hợp lệ')
                if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                    raise ValueError('Không hỗ trợ liên kết hoặc ZIP mã hóa')
                path = target/name
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                digest = hashlib.sha256()
                with z.open(info) as source, path.open('xb') as output:
                    while chunk := source.read(1_048_576):
                        digest.update(chunk)
                        output.write(chunk)
                path.chmod(0o600)
                if digest.hexdigest() != manifest['files'][name]:
                    raise ValueError('Checksum của bản sao lưu không khớp')
        database = target/'database.sqlite3'
        verify_sqlite(database)
        from backend.scripts.migrate_db import migrate
        migrate(database)
        with closing(sqlite3.connect(database)) as conn:
            documents = conn.execute('SELECT storage_key, sha256, byte_size FROM documents').fetchall()
            for key, digest, size in documents:
                if not SAFE_UPLOAD.fullmatch(key):
                    raise ValueError('Tên tệp chứng từ không hợp lệ')
                file = target/'uploads'/key
                if not file.is_file() or file.stat().st_size != size or file_hash(file) != digest:
                    raise ValueError('Bản sao lưu thiếu hoặc sai chứng từ')
            conn.execute('UPDATE auth_sessions SET revoked_at=?',
                         (datetime.now(timezone.utc).isoformat(),))
            conn.commit()
        settings = json.loads((target/'settings.json').read_text())
        if not isinstance(settings, dict) or any(k not in SAFE_SETTINGS or not isinstance(v, str) for k, v in settings.items()):
            raise ValueError('Cấu hình sao lưu không hợp lệ')
        current = read_config(active_config)
        current.update(settings)
        current.update(SUNNY_ERP_DB=str(database), SUNNY_UPLOAD_DIR=str(target/'uploads'),
                       SUNNY_JWT_SECRET=secrets.token_urlsafe(48))
        (target/'uploads').mkdir(exist_ok=True, mode=0o700)
        verify_sqlite(database)
        from backend.app.core.config import Settings
        try:Settings.from_mapping(current)
        except RuntimeError as exc:raise ValueError(str(exc)) from None
        from backend.scripts.check_db_integrity import check
        if not check(database)['passed']:raise ValueError('Sổ nghiệp vụ chưa đối soát khớp; chưa chuyển dữ liệu đang dùng')
        write_config(active_config, current)
        switched = True
        return {'restored': True, 'profile': target.name, 'documents': len(documents),
                'old_data_retained': True, 'sessions_revoked': True}
    finally:
        if not switched:
            shutil.rmtree(target, ignore_errors=True)
