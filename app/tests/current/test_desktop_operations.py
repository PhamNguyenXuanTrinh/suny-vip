from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
import hashlib
import io
import json
import sqlite3
import threading
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.scripts.desktop import Controller, InstanceLock, handler_for
from backend.scripts.maintenance import create_backup, read_config, restore_backup

PASSWORD = 'Desktop-test-password-2026!'


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    controller = Controller(tmp_path/'machine')
    monkeypatch.setattr(controller, 'start', lambda: {'running': True})
    controller.setup({'username': 'owner', 'password': PASSWORD,
                      'confirmation': PASSWORD, 'organization_name': 'SUNNY thử nghiệm'})
    return controller


def client_for(config):
    values = read_config(config)
    settings = Settings(Path(values['SUNNY_ERP_DB']), values['SUNNY_JWT_SECRET'], Path(values['SUNNY_UPLOAD_DIR']))
    return TestClient(create_app(settings))


def headers(client):
    result = client.post('/api/v1/auth/login', json={'username': 'owner', 'password': PASSWORD})
    assert result.status_code == 200
    return {'Authorization': 'Bearer '+result.json()['access_token']}


def test_full_backup_restore_preserves_documents_and_retains_original(desktop):
    with client_for(desktop.config) as c:
        h = headers(c)
        assert c.post('/api/v1/auth/change-password', headers=h,
                      json={'current_password': PASSWORD, 'new_password': PASSWORD+'2'}).status_code == 200
        login = c.post('/api/v1/auth/login', json={'username': 'owner', 'password': PASSWORD+'2'}).json()
        h = {'Authorization': 'Bearer '+login['access_token']}
        assert c.post('/api/v1/customers', headers=h, json={'customer_code': 'PRESERVE', 'name': 'Khách trước sao lưu'}).status_code == 201
        png = io.BytesIO()
        Image.new('RGB', (2, 2)).save(png, 'PNG')
        uploaded = c.post('/api/v1/documents/upload', headers=h, files={'file': ('invoice.png', png.getvalue(), 'image/png')})
        assert uploaded.status_code == 201
        backup = desktop.backup()
        assert c.post('/api/v1/customers', headers=h, json={'customer_code': 'AFTER', 'name': 'Khách sau sao lưu'}).status_code == 201
    previous = read_config(desktop.config)
    archive = desktop.root/'backups'/backup['name']
    with zipfile.ZipFile(archive) as z:
        settings = z.read('settings.json').decode()
        assert 'SUNNY_JWT_SECRET' not in settings and 'OPENAI_API_KEY' not in settings
        assert len([n for n in z.namelist() if n.startswith('uploads/')]) == 1
    result = restore_backup(archive, desktop.root, desktop.config)
    current = read_config(desktop.config)
    assert result['old_data_retained'] and current['SUNNY_ERP_DB'] != previous['SUNNY_ERP_DB']
    assert current['SUNNY_JWT_SECRET'] != previous['SUNNY_JWT_SECRET']
    assert Path(previous['SUNNY_ERP_DB']).is_file()
    with closing(sqlite3.connect(current['SUNNY_ERP_DB'])) as conn:
        assert conn.execute('SELECT customer_code FROM customers').fetchall() == [('PRESERVE',)]
        assert conn.execute('SELECT COUNT(*) FROM auth_sessions WHERE revoked_at IS NULL').fetchone()[0] == 0
    with client_for(desktop.config) as c:
        assert c.get('/api/v1/auth/me', headers=h).status_code == 401
        fresh = c.post('/api/v1/auth/login', json={'username': 'owner', 'password': PASSWORD+'2'}).json()
        r = c.get('/api/v1/documents/'+uploaded.json()['id']+'/download', headers={'Authorization': 'Bearer '+fresh['access_token']})
        assert r.status_code == 200 and r.content == png.getvalue()


@pytest.mark.parametrize('mode', ['checksum', 'traversal', 'extra_file', 'missing_document'])
def test_restore_rejects_damaged_archives_without_switching_live_config(desktop, mode):
    good = desktop.root/'backups'/desktop.backup()['name']
    bad = desktop.root/'backups'/('bad-'+mode+'.sunnybackup')
    with zipfile.ZipFile(good) as z:
        entries = {i.filename: z.read(i) for i in z.infolist()}
    manifest = json.loads(entries['backup.json'])
    if mode == 'checksum':
        entries['database.sqlite3'] += b'corruption'
    elif mode == 'traversal':
        entries['../outside.txt'] = b'no'
        manifest['files']['../outside.txt'] = hashlib.sha256(b'no').hexdigest()
    elif mode == 'extra_file':
        entries['unlisted.txt'] = b'no'
    else:
        # A self-consistent ZIP may still contain a database referring to absent attachments.
        temporary = desktop.root/'test-copy.sqlite3'
        temporary.write_bytes(entries['database.sqlite3'])
        with closing(sqlite3.connect(temporary)) as conn:
            import uuid
            org, user = conn.execute('SELECT organization_id,id FROM app_users LIMIT 1').fetchone()
            conn.execute("INSERT INTO documents(id,organization_id,original_name,media_type,byte_size,storage_key,sha256,uploaded_by,source_kind,received_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (str(uuid.uuid4()), org, 'missing.png', 'image/png', 2, 'a'*32+'.png', '0'*64, user, 'general', '2026-10-26T00:00:00Z', '2026-10-26T00:00:00Z'))
            conn.commit()
        entries['database.sqlite3'] = temporary.read_bytes()
        manifest['files']['database.sqlite3'] = hashlib.sha256(entries['database.sqlite3']).hexdigest()
    entries['backup.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bad, 'w') as z:
        for name, value in entries.items():
            z.writestr(name, value)
    before = desktop.config.read_bytes()
    with pytest.raises(ValueError):
        restore_backup(bad, desktop.root, desktop.config)
    assert desktop.config.read_bytes() == before
    assert not (desktop.root/'outside.txt').exists()


def test_backup_missing_attachment_fails_without_partial_backup(desktop):
    with client_for(desktop.config) as c:
        h = headers(c)
        assert c.post('/api/v1/auth/change-password', headers=h, json={'current_password': PASSWORD, 'new_password': PASSWORD+'3'}).status_code == 200
        fresh = c.post('/api/v1/auth/login', json={'username': 'owner', 'password': PASSWORD+'3'}).json()
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, 'PNG')
        assert c.post('/api/v1/documents/upload', headers={'Authorization': 'Bearer '+fresh['access_token']}, files={'file': ('x.png', stream.getvalue(), 'image/png')}).status_code == 201
    uploads = Path(read_config(desktop.config)['SUNNY_UPLOAD_DIR'])
    next(uploads.iterdir()).unlink()
    with pytest.raises(ValueError):
        desktop.backup()
    assert not list((desktop.root/'backups').glob('*.sunnybackup'))


def test_local_control_requires_private_session_csrf_and_local_origin(tmp_path, monkeypatch):
    control = Controller(tmp_path/'local')
    monkeypatch.setattr(control, 'start', lambda: {'running': True})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(control))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.get('/api/status').status_code == 401
            assert client.get('/?token='+control.token, headers={'Host': 'attacker.test'}).status_code == 403
            assert client.get('/?token='+control.token).status_code == 200
            assert client.get('/api/status').json()['configured'] is False
            body = {'username': 'owner', 'password': PASSWORD, 'confirmation': PASSWORD, 'organization_name': 'SUNNY'}
            assert client.post('/api/setup', json=body).status_code == 403
            assert client.post('/api/setup', json=body, headers={'Origin': 'https://attacker.test', 'X-Sunny-CSRF': control.token}).status_code == 403
            assert client.post('/api/setup', json=body, headers={'Origin': base, 'X-Sunny-CSRF': 'wrong'}).status_code == 403
            valid = {'Origin': base, 'X-Sunny-CSRF': control.token}
            assert client.post('/api/setup', json=body, headers=valid).status_code == 200
            assert client.post('/api/setup', json=body, headers=valid).status_code == 400
            state = client.get('/api/status').json()
            assert state['configured'] is True
            assert PASSWORD not in json.dumps(state) and 'SUNNY_JWT_SECRET' not in json.dumps(state)
            assert client.post('/api/restore', json={'name': '../outside.sunnybackup', 'confirmation': 'KHOI PHUC'}, headers=valid).status_code == 400
    finally:
        server.shutdown()
        server.server_close()


def test_second_launcher_does_not_take_the_same_data_lock(tmp_path):
    path = tmp_path/'desktop.lock'
    lock = InstanceLock(path)
    try:
        with pytest.raises(RuntimeError):
            InstanceLock(path)
    finally:
        lock.close()
    InstanceLock(path).close()


def test_automatic_retention_does_not_remove_manual_backups(desktop):
    folder = desktop.root/'backups'
    manual = desktop.backup()['name']
    for _ in range(9):
        desktop.backup(automatic=True)
    assert len(list(folder.glob('auto-*.sunnybackup'))) == 7
    assert (folder/manual).is_file()


@pytest.mark.parametrize('setting,value',[('SUNNY_BUSINESS_TIMEZONE','Invalid/Factory'),('SUNNY_MAX_SESSIONS','0'),('SUNNY_ALERT_INTERVAL_SECONDS','oops'),('SUNNY_RECEIPT_SPIKE_THRESHOLDS','{"CEMENT":{"factor":"NaN"}}')])
def test_restore_invalid_settings_never_replaces_working_profile(desktop,setting,value):
    good=desktop.root/'backups'/desktop.backup()['name'];bad=desktop.root/'bad-settings.sunnybackup'
    with zipfile.ZipFile(good) as z:entries={i.filename:z.read(i) for i in z.infolist()}
    settings=json.loads(entries['settings.json']);settings[setting]=value;entries['settings.json']=json.dumps(settings).encode()
    manifest=json.loads(entries['backup.json']);manifest['files']['settings.json']=hashlib.sha256(entries['settings.json']).hexdigest();entries['backup.json']=json.dumps(manifest).encode()
    with zipfile.ZipFile(bad,'w') as z:
        for name,content in entries.items():z.writestr(name,content)
    before=desktop.config.read_bytes()
    with pytest.raises(ValueError):restore_backup(bad,desktop.root,desktop.config)
    assert desktop.config.read_bytes()==before


def test_backup_creation_enforces_same_limit_as_restore(desktop,monkeypatch):
    from backend.scripts import maintenance
    monkeypatch.setattr(maintenance,'MAX_UNPACKED',100)
    with pytest.raises(ValueError,match='4 GB'):desktop.backup()
    assert not list((desktop.root/'backups').glob('*.sunnybackup'))
