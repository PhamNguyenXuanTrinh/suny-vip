"""Local control center and first-run setup for the bundled ERP server.

The control center binds only to loopback and requires a random private token.
It is a machine-operator surface, never a tenant-admin ERP endpoint.
"""
from contextlib import closing
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import argparse
import hmac
import ipaddress
import json
import os
import re
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile

from backend.app.core.config import ROOT
from backend.scripts.maintenance import (create_backup, private_write, read_config,
                                        restore_backup, write_config)


def default_data_dir():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'SUNNY_GROUP'/'FLEX3D_ERP'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'sunny-flex3d-erp'


class InstanceLock:
    def __init__(self, path):
        self.stream = Path(path).open('a+b')
        self.stream.seek(0)
        if Path(path).stat().st_size == 0:
            self.stream.write(b'1')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('SUNNY ERP đang mở với thư mục dữ liệu này') from None

    def close(self):
        self.stream.close()


class Controller:
    def __init__(self, data_dir, port=8765, no_browser=False):
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.config = self.root/'config.env'
        self.options_file = self.root/'desktop.json'
        self.port = port
        self.options = {'lan_enabled': False}
        if self.options_file.is_file():
            self.options.update(json.loads(self.options_file.read_text()))
        self.token = secrets.token_urlsafe(48)
        self.no_browser = no_browser
        self.process = None
        self.log_stream = None
        self.operation_lock = threading.RLock()
        self.error = ''
        self.closed = threading.Event()
        self.http = None
        self.last_auto_backup = None

    def is_configured(self):
        if not self.config.is_file():
            return False
        values = read_config(self.config)
        database = Path(values.get('SUNNY_ERP_DB', ''))
        if not database.is_file():
            return False
        with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as conn:
            return conn.execute('SELECT COUNT(*) FROM app_users').fetchone()[0] > 0

    def setup(self, body):
        with self.operation_lock:
            if self.is_configured():
                raise ValueError('Đã có tài khoản quản trị; không thể thiết lập lại')
            username = str(body.get('username', '')).strip().lower()
            password = body.get('password', '')
            name = str(body.get('organization_name', '')).strip()
            if not re.fullmatch(r'[a-z0-9_.-]{3,64}', username):
                raise ValueError('Tên đăng nhập cần 3–64 ký tự chữ, số, dấu chấm hoặc gạch')
            if not isinstance(password, str) or not 12 <= len(password) <= 128:
                raise ValueError('Mật khẩu cần từ 12 đến 128 ký tự')
            if password != body.get('confirmation'):
                raise ValueError('Hai mật khẩu không trùng nhau')
            if not 1 <= len(name) <= 200:
                raise ValueError('Tên doanh nghiệp cần từ 1 đến 200 ký tự')
            from backend.scripts.migrate_db import migrate
            from backend.scripts.create_admin import provision
            from backend.app.database import make_engine
            if not self.config.exists():
                live = self.root/'profiles/live'
                write_config(self.config, {
                    'SUNNY_JWT_SECRET': secrets.token_urlsafe(48),
                    'SUNNY_ERP_DB': str(live/'database/sunny.sqlite3'),
                    'SUNNY_UPLOAD_DIR': str(live/'uploads'),
                    'SUNNY_ALLOWED_ORIGINS': f'http://127.0.0.1:{self.port}',
                    'SUNNY_OPENAI_MODEL': 'gpt-4o', 'SUNNY_ALERT_INTERVAL_SECONDS': '300',
                    'SUNNY_BUSINESS_TIMEZONE': 'Asia/Ho_Chi_Minh',
                    'OPENAI_API_KEY': ''})
            values = read_config(self.config)
            migrate(values['SUNNY_ERP_DB'])
            engine = make_engine('sqlite:///'+values['SUNNY_ERP_DB'])
            try:
                provision(engine, 'SUNNY', name, username, password, True)
            finally:
                engine.dispose()
            self.options['lan_enabled'] = body.get('lan_enabled') is True
            self.save_options()
            self.start()
            return {'configured': True, 'must_change_password': True}

    def save_options(self):
        private_write(self.options_file, json.dumps(self.options).encode())

    def start(self):
        with self.operation_lock:
            if self.process and self.process.poll() is None:
                return {'running': True}
            if not self.is_configured():
                raise ValueError('Hãy thiết lập tài khoản quản trị trước')
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(('0.0.0.0' if self.options['lan_enabled'] else '127.0.0.1', self.port))
                except OSError:
                    raise ValueError(f'Cổng {self.port} đang được sử dụng; chưa khởi động máy chủ mới') from None
            logs = self.root/'logs'
            logs.mkdir(exist_ok=True, mode=0o700)
            log = logs/'server.log'
            if log.exists() and log.stat().st_size > 5_000_000:
                old = logs/'server.previous.log'
                old.unlink(missing_ok=True)
                log.rename(old)
            self.log_stream = log.open('ab')
            environment = os.environ.copy()
            environment.update(read_config(self.config))
            instance = secrets.token_hex(16)
            environment.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', SUNNY_INSTANCE_ID=instance)
            kwargs = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
            self.process = subprocess.Popen(
                [sys.executable, '-m', 'backend.scripts.run_server', '--config', str(self.config),
                 '--host', '0.0.0.0' if self.options['lan_enabled'] else '127.0.0.1', '--port', str(self.port)],
                cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=self.log_stream, stderr=self.log_stream, **kwargs)
            for _ in range(180):
                if self.process.poll() is not None:
                    self.stop()
                    raise ValueError('Máy chủ chưa chạy được. Xem nhật ký tại '+str(log))
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/api/v1/health', timeout=.5) as response:
                        if response.status == 200 and json.load(response).get('instance_id') == instance:
                            self.error = ''
                            return {'running': True}
                except (OSError, ValueError):
                    pass
                time.sleep(.2)
            self.stop()
            raise ValueError('Máy chủ khởi động quá lâu. Xem nhật ký tại '+str(log))

    def stop(self):
        with self.operation_lock:
            if self.process:
                if self.process.poll() is None:
                    try:
                        self.process.send_signal(signal.CTRL_BREAK_EVENT) if os.name == 'nt' else self.process.terminate()
                        self.process.wait(timeout=10)
                    except (OSError, subprocess.TimeoutExpired):
                        self.process.kill()
                        self.process.wait(timeout=5)
                self.process = None
            if self.log_stream:
                self.log_stream.close()
                self.log_stream = None
            return {'running': False}

    def backup(self, automatic=False):
        with self.operation_lock:
            if not self.is_configured():
                raise ValueError('Chưa có dữ liệu để sao lưu')
            result = create_backup(self.config, self.root/'backups', automatic)
            if automatic:
                self.last_auto_backup = datetime.now(timezone.utc).date()
                # Only generated auto-backups are retained for seven copies.
                # Manual backups are never removed by this routine.
                old = sorted((self.root/'backups').glob('auto-*.sunnybackup'), reverse=True)[7:]
                for path in old:
                    path.unlink()
            return result

    def restore(self, body):
        with self.operation_lock:
            name = str(body.get('name', ''))
            if body.get('confirmation') != 'KHOI PHUC':
                raise ValueError('Nhập KHOI PHUC để xác nhận thay dữ liệu đang dùng')
            if Path(name).name != name or not re.fullmatch(r'[A-Za-z0-9_.-]+\.sunnybackup', name):
                raise ValueError('Tên bản sao lưu không hợp lệ')
            archive = self.root/'backups'/name
            if not archive.is_file() or archive.is_symlink():
                raise ValueError('Không tìm thấy bản sao lưu')
            was_running = self.process is not None and self.process.poll() is None
            self.stop()
            try:
                safety = self.backup()
                result = restore_backup(archive, self.root, self.config)
            except Exception:
                if was_running:
                    self.start()
                raise
            self.start()
            result['safety_backup'] = safety['name']
            return result

    def status(self):
        with self.operation_lock:
            running = bool(self.process and self.process.poll() is None)
            backups = sorted((self.root/'backups').glob('*.sunnybackup'), reverse=True)
            addresses = []
            if self.options['lan_enabled']:
                try:
                    for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                        ip = ipaddress.ip_address(item[4][0])
                        if ip.is_private and not ip.is_loopback:
                            addresses.append(f'http://{ip}:{self.port}')
                except OSError:
                    pass
            return {'configured': self.is_configured(), 'running': running,
                    'local_url': f'http://127.0.0.1:{self.port}', 'lan_urls': sorted(set(addresses)),
                    'lan_enabled': bool(self.options['lan_enabled']), 'data_directory': str(self.root),
                    'error': self.error, 'backups': [{'name': p.name, 'bytes': p.stat().st_size} for p in backups],
                    'last_auto_backup': str(self.last_auto_backup) if self.last_auto_backup else None,
                    'version': '2.1.0'}

    def dispatch(self, action, body):
        if action == 'setup':
            return self.setup(body)
        if action == 'start':
            return self.start()
        if action == 'stop':
            return self.stop()
        if action == 'backup':
            return self.backup()
        if action == 'restore':
            return self.restore(body)
        if action == 'lan':
            with self.operation_lock:
                self.stop()
                self.options['lan_enabled'] = body.get('enabled') is True
                self.save_options()
                return self.start()
        if action == 'exit':
            self.closed.set()
            return {'closing': True}
        raise ValueError('Thao tác không được hỗ trợ')

    def background(self):
        if self.is_configured():
            try:
                self.start()
            except Exception as exc:
                self.error = str(exc)
        while not self.closed.wait(15):
            try:
                if self.process and self.process.poll() is None and self.last_auto_backup != datetime.now(timezone.utc).date():
                    self.backup(automatic=True)
            except Exception as exc:
                self.error = 'Sao lưu tự động chưa thành công: '+str(exc)


def handler_for(controller):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass  # Never log a setup token or submitted credential.

        def reply(self, code, data, content='application/json; charset=utf-8', cookie=False):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            if code >= 400:
                # A rejected POST may still have an unread body on the wire.
                # Do not interpret those bytes as a second HTTP request.
                self.close_connection = True
                self.send_header('Connection', 'close')
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-"+controller.token+"'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            if cookie:
                self.send_header('Set-Cookie', 'sunny_control='+controller.token+'; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(raw)

        def local_request(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return self.client_address[0] == '127.0.0.1' and self.headers.get('Host') == expected

        def authenticated(self):
            try:
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                value = cookies.get('sunny_control')
                return value is not None and hmac.compare_digest(value.value, controller.token)
            except Exception:
                return False

        def do_GET(self):
            if not self.local_request():
                return self.reply(403, {'error': 'Chỉ mở trên máy chủ SUNNY'})
            path = urlsplit(self.path)
            token = parse_qs(path.query).get('token', [''])[0]
            if path.path == '/' and (self.authenticated() or hmac.compare_digest(token, controller.token)):
                source = (ROOT/'backend/static/desktop/index.html').read_text(encoding='utf-8')
                return self.reply(200, source.replace('__SUNNY_TOKEN__', controller.token).encode(), 'text/html; charset=utf-8', True)
            if not self.authenticated():
                return self.reply(401, {'error': 'Mở Bảng điều khiển bằng biểu tượng SUNNY ERP trên máy chủ'})
            if path.path == '/api/status':
                return self.reply(200, controller.status())
            return self.reply(404, {'error': 'Không tìm thấy'})

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if (not self.local_request() or not self.authenticated() or self.headers.get('Origin') != origin
                or not hmac.compare_digest(self.headers.get('X-Sunny-CSRF', ''), controller.token)):
                return self.reply(403, {'error': 'Yêu cầu không hợp lệ'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192 or self.headers.get_content_type() != 'application/json':
                    return self.reply(413, {'error': 'Yêu cầu quá lớn hoặc sai định dạng'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('Dữ liệu không hợp lệ')
                path = urlsplit(self.path).path
                if not path.startswith('/api/'):
                    return self.reply(404, {'error': 'Không tìm thấy'})
                result = controller.dispatch(path[5:], body)
                return self.reply(200, result)
            except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
                return self.reply(400, {'error': str(exc)})
            except Exception:
                return self.reply(500, {'error': 'Không thực hiện được. Kiểm tra nhật ký và giữ bản sao lưu hiện có.'})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=default_data_dir())
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit('Cổng máy chủ cần trong khoảng 1024–65535')
    controller = Controller(args.data_dir, args.port, args.no_browser)
    session = controller.root/'desktop-session.json'
    try:
        lock = InstanceLock(controller.root/'desktop.lock')
    except RuntimeError:
        if session.is_file():
            data = json.loads(session.read_text())
            if not args.no_browser:
                webbrowser.open(data['url'])
            print('SUNNY ERP đang chạy. Đã mở Bảng điều khiển hiện có.')
            return
        raise
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(controller))
    server.daemon_threads = True
    controller.http = server
    url = f'http://127.0.0.1:{server.server_port}/?token={controller.token}'
    private_write(session, json.dumps({'pid': os.getpid(), 'url': url}).encode())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=controller.background, daemon=True).start()
    print('SUNNY ERP — Bảng điều khiển đã sẵn sàng trên máy chủ.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    def close(*_):
        controller.closed.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, close)
    try:
        controller.closed.wait()
    finally:
        controller.stop()
        server.shutdown()
        server.server_close()
        session.unlink(missing_ok=True)
        lock.close()


if __name__ == '__main__':
    main()
