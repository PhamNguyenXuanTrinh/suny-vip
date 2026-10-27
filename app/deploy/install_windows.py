"""Offline per-user installation of a verified SUNNY Windows bundle."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid


def verify(source):
    source = Path(source).resolve()
    manifest = json.loads((source/'BUNDLE_SHA256.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'sunny-offline-bundle-v1':
        raise ValueError('Không đúng định dạng bộ cài SUNNY')
    for relative, digest in manifest['files'].items():
        path = (source/relative).resolve()
        if not path.is_relative_to(source) or path.is_symlink() or not path.is_file():
            raise ValueError('Bộ cài thiếu tệp: '+relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Tệp trong bộ cài không khớp: '+relative)
    for name in ('runtime/windows/python.exe', 'runtime/windows/pythonw.exe',
                 'app/frontend/dist/index.html', 'app/backend/scripts/desktop.py'):
        if name not in manifest['files']:
            raise ValueError('Bộ cài thiếu thành phần chạy: '+name)
    return manifest


def install(source, destination=None, shortcut=True, launch=True):
    if sys.platform != 'win32':
        raise ValueError('Bộ cài này dành cho Windows 64-bit')
    source = Path(source).resolve()
    manifest = verify(source)
    release = manifest['version']+'-'+hashlib.sha256((source/'BUNDLE_SHA256.json').read_bytes()).hexdigest()[:12]
    base = Path(destination) if destination else Path(os.environ['LOCALAPPDATA'])/'Programs/SUNNYERP'
    releases = base.resolve()/'releases'
    releases.mkdir(parents=True, exist_ok=True)
    target = releases/release
    if target.exists():
        verify(target)
    else:
        temp = releases/('.install-'+uuid.uuid4().hex)
        try:
            temp.mkdir()
            for relative in [*manifest['files'], 'BUNDLE_SHA256.json']:
                out = temp/relative
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source/relative, out)
            verify(temp)
            temp.rename(target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    if shortcut:
        environment = os.environ.copy()
        environment.update(SUNNY_EXE=str(target/'runtime/windows/pythonw.exe'),
                           SUNNY_CWD=str(target/'app'))
        script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'SUNNY ERP.lnk'));$s.TargetPath=$env:SUNNY_EXE;$s.Arguments='-m backend.scripts.desktop';$s.WorkingDirectory=$env:SUNNY_CWD;$s.Description='SUNNY AI FLEX 3D ERP';$s.Save()"
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                        "$ErrorActionPreference='Stop';"+script], env=environment, check=True)
    if launch:
        subprocess.Popen([str(target/'runtime/windows/pythonw.exe'), '-m', 'backend.scripts.desktop'],
                         cwd=target/'app', creationflags=subprocess.DETACHED_PROCESS)
    return {'installed': True, 'directory': str(target), 'files_verified': len(manifest['files']),
            'desktop_shortcut': shortcut, 'separate_user_data': True,
            'python_installation_required': False, 'internet_required_for_erp': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--no-shortcut', action='store_true')
    parser.add_argument('--no-launch', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.source, args.destination, not args.no_shortcut, not args.no_launch), ensure_ascii=False))
    except Exception as exc:
        print('Không cài được SUNNY ERP: '+str(exc), file=sys.stderr)
        raise SystemExit(1)
