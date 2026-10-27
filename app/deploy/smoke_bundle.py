"""Exercise the extracted offline bundle against fresh, disposable local data."""
from importlib import metadata
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import argparse
import hashlib
import io
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time

import httpx
from PIL import Image
from deploy.install_windows import verify


def windows_runtime_audit(bundle):
    root = bundle/'runtime/windows'
    packages = root/'Lib/site-packages'
    distributions = list(metadata.distributions(path=[str(packages)]))
    installed = {canonicalize_name(d.metadata['Name']): d.version for d in distributions}
    env = default_environment()
    env.update(os_name='nt', sys_platform='win32', platform_system='Windows',
               platform_machine='AMD64', python_version='3.13', python_full_version='3.13.17',
               implementation_name='cpython', platform_python_implementation='CPython', extra='')
    for distribution in distributions:
        for raw in distribution.requires or []:
            required = Requirement(raw)
            if not required.marker or required.marker.evaluate(env):
                version = installed.get(canonicalize_name(required.name))
                if not version or version not in required.specifier:
                    raise ValueError('Missing Windows runtime dependency: '+str(required))
    binaries = []
    for file in root.rglob('*'):
        if file.suffix.lower() in {'.exe', '.dll', '.pyd'}:
            data = file.read_bytes()
            offset = struct.unpack_from('<I', data, 0x3c)[0]
            if data[:2] != b'MZ' or data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0x8664:
                raise ValueError('Invalid Windows x64 binary: '+file.name)
            binaries.append(file)
    if list(root.rglob('*.so')):
        raise ValueError('A host Linux library entered the Windows runtime')
    if '../../app' not in (root/'python313._pth').read_text():
        raise ValueError('Embedded Python cannot find the bundled application')
    return {'runtime_packages': len(distributions), 'dependency_errors': [],
            'windows_x64_binaries': len(binaries), 'host_libraries_included': False,
            'native_windows_execution': False}


def smoke(bundle):
    bundle = Path(bundle).resolve()
    if not Path(sys.executable).resolve().is_relative_to(bundle/'runtime/linux'):
        raise ValueError('Run this check with the extracted bundle Python, not host Python')
    manifest = verify(bundle)
    audit = windows_runtime_audit(bundle)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='sunny-offline-smoke-') as temp:
        state = Path(temp)
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith('SUNNY_') and k not in ('OPENAI_API_KEY', 'PYTHONPATH', 'PYTHONHOME')}
        environment.update(OPENAI_API_KEY='', PYTHONDONTWRITEBYTECODE='1',
                           HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
                           NO_PROXY='127.0.0.1,localhost')
        process = subprocess.Popen(['bash', str(bundle/'MO_LINUX.sh'), '--no-browser',
                                    '--data-dir', str(state), '--port', str(port)],
                                   cwd=bundle, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            session = state/'desktop-session.json'
            for _ in range(180):
                if session.is_file():
                    break
                if process.poll() is not None:
                    raise ValueError('Bundle launcher exited before setup')
                time.sleep(.1)
            connection = json.loads(session.read_text())
            url = urlsplit(connection['url'])
            token = parse_qs(url.query)['token'][0]
            origin = url.scheme+'://'+url.netloc
            with httpx.Client(base_url=origin, trust_env=False, timeout=60) as control:
                assert control.get(connection['url']).status_code == 200
                headers = {'Origin': origin, 'X-Sunny-CSRF': token}
                password = secrets.token_urlsafe(24)
                result = control.post('/api/setup', headers=headers,
                    json={'organization_name':'SUNNY nghiệm thu bộ cài','username':'bundle_owner',
                          'password':password,'confirmation':password})
                assert result.status_code == 200, result.text
                assert control.get('/api/status').json()['running']
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as app:
                    tokens = app.post('/api/v1/auth/login', json={'username':'bundle_owner','password':password}).json()
                    h = {'Authorization':'Bearer '+tokens['access_token']}
                    assert tokens['must_change_password'] and app.get('/api/v1/customers',headers=h).status_code == 403
                    new_password = secrets.token_urlsafe(28)
                    assert app.post('/api/v1/auth/change-password',headers=h,json={'current_password':password,'new_password':new_password}).status_code == 200
                    tokens = app.post('/api/v1/auth/login',json={'username':'bundle_owner','password':new_password}).json()
                    h = {'Authorization':'Bearer '+tokens['access_token']}
                    assert app.post('/api/v1/customers',headers=h,json={'customer_code':'BUNDLE','name':'Dữ liệu trước sao lưu'}).status_code == 201
                    stream = io.BytesIO()
                    Image.new('RGB',(2,2)).save(stream,'PNG')
                    upload = app.post('/api/v1/documents/upload',headers=h,files={'file':('proof.png',stream.getvalue(),'image/png')})
                    assert upload.status_code == 201
                    assert app.get('/').status_code == 200 and app.get('/api/docs').status_code == 200
                    assert app.get('/api/v1/ai/status',headers=h).json()['configured'] is False
                    backup = control.post('/api/backup',headers=headers,json={})
                    assert backup.status_code == 200, backup.text
                    assert app.post('/api/v1/customers',headers=h,json={'customer_code':'AFTER','name':'Dữ liệu sau sao lưu'}).status_code == 201
                    restored = control.post('/api/restore',headers=headers,
                                             json={'name':backup.json()['name'],'confirmation':'KHOI PHUC'})
                    assert restored.status_code == 200, restored.text
                    assert restored.json()['old_data_retained']
                    assert app.get('/api/v1/auth/me',headers=h).status_code == 401
                    tokens = app.post('/api/v1/auth/login',json={'username':'bundle_owner','password':new_password}).json()
                    h = {'Authorization':'Bearer '+tokens['access_token']}
                    assert app.get('/api/v1/customers',headers=h).json()['total'] == 1
                    content = app.get('/api/v1/documents/'+upload.json()['id']+'/download',headers=h)
                    assert content.status_code == 200 and hashlib.sha256(content.content).digest() == hashlib.sha256(stream.getvalue()).digest()
                assert control.post('/api/exit',headers=headers,json={}).status_code == 200
            process.wait(timeout=20)
            assert process.returncode == 0
            return {'passed':True,'manifest_files_verified':len(manifest['files']),
                    'python':sys.version.split()[0], 'python_path_in_bundle':True,
                    'runtime_requires_host_python_or_node':False,'fresh_private_data':True,
                    'browser_setup_server_start':True,'forced_password_change':True,
                    'authenticated_crud':True,'private_document_upload_download':True,
                    'complete_backup_restore':True,'restored_snapshot_correct':True,
                    'previous_data_retained':True,'previous_sessions_revoked':True,
                    'frontend_and_local_api_docs':True,'erp_without_api_key':True,
                    'outbound_http_proxy_disabled_for_test':True,
                    'windows_runtime_audit':audit,'actual_windows_execution':False,
                    'actual_production_data':False}
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--evidence',type=Path)
    args = p.parse_args()
    result = smoke(args.bundle)
    text = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.evidence:
        args.evidence.write_text(text,encoding='utf-8')
    print(text)
