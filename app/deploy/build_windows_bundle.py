"""Build the complete offline Windows distribution from verified components.

Prepare the packages directory with pip --target --platform win_amd64
--python-version 3.13 --implementation cp --abi cp313 --only-binary=:all:
-r deploy/requirements.windows.lock.txt. No credentials or customer data enter it.
"""
from importlib import metadata
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.2.0'
PYTHON_URL = 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'
PYTHON_SHA256 = '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
EXCLUDE = {'.venv', 'node_modules', 'runtime', 'data', '__pycache__', '.pytest_cache',
           '.git', 'test-results', 'playwright-report'}


def source_files():
    vite_manifest=ROOT/'frontend/dist/asset-manifest.json'
    if not vite_manifest.is_file():raise ValueError('Build the frontend before packaging')
    assets={'index.html','asset-manifest.json'}
    for entry in json.loads(vite_manifest.read_text()).values():
        assets.add(entry['file']);assets.update(entry.get('css',[]));assets.update(entry.get('assets',[]))
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[:2]==('docs','current') and relative.name in {'backend_tests.xml','backend_test_output.txt','clean_install_check.json'}:
            continue
        if relative.parts[:2]==('frontend','dist') and relative.relative_to('frontend/dist').as_posix() not in assets:
            continue
        if any(p in EXCLUDE for p in relative.parts):
            continue
        if path.name in {'.env', '.env.local', 'CURRENT_SHA256.json'} or path.suffix in {'.pyc', '.sqlite3', '.db', '.bak'}:
            continue
        if path.is_symlink():
            raise ValueError('Source symlink: '+str(relative))
        if path.suffix in {'.py', '.js', '.json', '.ts', '.tsx', '.md', '.txt', '.html'}:
            if re.search(rb'sk-(?:proj-)?[A-Za-z0-9_-]{35,}|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{36}', path.read_bytes()):
                raise ValueError('Inspect potential secret privately in '+str(relative))
        yield path, relative


def frontend_licenses(destination):
    modules = ROOT/'frontend/node_modules'
    manifest = json.loads((ROOT/'frontend/package.json').read_text())
    pending = list(manifest['dependencies'])
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        package = modules/name
        info = json.loads((package/'package.json').read_text())
        folder = destination/(name.replace('/', '__')+'-'+info['version'])
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'package.json').write_text(json.dumps({k: info[k] for k in ('name', 'version', 'license', 'author', 'repository') if k in info}, ensure_ascii=False, indent=2))
        found = False
        for path in package.iterdir():
            if path.is_file() and path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
                shutil.copyfile(path, folder/path.name)
                found = True
        if not found:
            raise ValueError('Missing distributed frontend license: '+name)
        pending.extend(info.get('dependencies', {}))
    return sorted(seen)


def build(runtime_zip, packages, output, linux_runtime=None, linux_packages=None):
    runtime_zip, packages, output = Path(runtime_zip), Path(packages), Path(output).resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Choose a new staging directory outside the source tree')
    if hashlib.sha256(runtime_zip.read_bytes()).hexdigest() != PYTHON_SHA256:
        raise ValueError('Official Python runtime checksum does not match')
    output.mkdir(parents=True)
    app = output/'app'
    for source, relative in source_files():
        target = app/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    runtime = output/'runtime/windows'
    runtime.mkdir(parents=True)
    with zipfile.ZipFile(runtime_zip) as z:
        if z.testzip() is not None:
            raise ValueError('Damaged Python distribution')
        for info in z.infolist():
            if Path(info.filename).is_absolute() or '..' in Path(info.filename).parts:
                raise ValueError('Unsafe runtime entry')
        z.extractall(runtime)
    shutil.copytree(packages, runtime/'Lib/site-packages', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'bin'))
    (runtime/'python313._pth').write_text('python313.zip\n.\nLib/site-packages\n../../app\nimport site\n', encoding='utf-8')
    for file in ('CAI_DAT_WINDOWS.cmd', 'MO_SUNNY_ERP.cmd'):
        (output/file).write_bytes((ROOT/'deploy'/file).read_text().replace('\r\n', '\n').replace('\n', '\r\n').encode())
    if linux_runtime:
        if not linux_packages:
            raise ValueError('Linux runtime dependencies are required')
        linux = output/'runtime/linux'
        shutil.copytree(linux_runtime, linux, ignore=shutil.ignore_patterns(
            '__pycache__', '*.pyc', '.libpython*', 'pip', 'pip3*', 'pip-*.dist-info', 'ensurepip', 'EXTERNALLY-MANAGED'))
        shutil.copytree(linux_packages, linux/'lib/python3.13/site-packages', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'bin'))
        shutil.copyfile(ROOT/'deploy/MO_LINUX.sh', output/'MO_LINUX.sh')
        (output/'MO_LINUX.sh').chmod(0o755)
    shutil.copyfile(ROOT/'docs/current/HUONG_DAN_SU_DUNG.md', output/'HUONG_DAN_SU_DUNG.md')
    packages_info = []
    for distribution in metadata.distributions(path=[str(packages)]):
        m = distribution.metadata
        packages_info.append({'name': m['Name'], 'version': m['Version'],
                              'license': m.get('License-Expression') or m.get('License', ''),
                              'license_files': [str(p) for p in distribution.files or [] if 'licens' in str(p).lower()]})
    frontend = frontend_licenses(output/'THIRD_PARTY_LICENSES/frontend')
    provenance = {'application_version': VERSION, 'target': 'Windows x86_64',
                  'python': {'version': '3.13.17', 'url': PYTHON_URL, 'sha256': PYTHON_SHA256},
                  'runtime_dependencies': sorted(packages_info, key=lambda x: x['name'].lower()),
                  'frontend_runtime_packages': frontend,
                  'license_locations': ['runtime/windows/LICENSE.txt', 'runtime/windows/Lib/site-packages/*.dist-info', 'THIRD_PARTY_LICENSES/frontend'],
                  'customer_data_included': False, 'api_key_included': False,
                  'internet_required_for_erp': False, 'python_installation_required': False}
    if linux_runtime:
        provenance['linux_runtime'] = {'version': '3.13.16', 'architecture': 'x86_64 glibc',
            'source': 'python-build-standalone, downloaded and verified by uv',
            'url': 'https://github.com/astral-sh/python-build-standalone',
            'package_installer_included': False,
            'runtime_packages': sorted([{'name':d.metadata['Name'],'version':d.version}
                for d in metadata.distributions(path=[str(linux_packages)])], key=lambda x:x['name'].lower())}
    (output/'BUNDLE_INFO.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    source_manifest = {'format': 'sunny-source-sha256-v1', 'application': 'SUNNY AI FLEX 3D ERP '+VERSION,
                       'files': {str(p.relative_to(app)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(app.rglob('*')) if p.is_file()}}
    (app/'CURRENT_SHA256.json').write_text(json.dumps(source_manifest, ensure_ascii=False, indent=2)+'\n')
    manifest = {'format': 'sunny-offline-bundle-v1', 'version': VERSION,
                'files': {str(p.relative_to(output)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.rglob('*')) if p.is_file()}}
    (output/'BUNDLE_SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return {'staged': str(output), 'files': len(manifest['files'])+1,
            'uncompressed_bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),
            'runtime_packages': len(packages_info), 'offline_runtime_included': True}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--runtime-zip', required=True)
    p.add_argument('--packages-dir', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--linux-runtime')
    p.add_argument('--linux-packages')
    args = p.parse_args()
    print(json.dumps(build(args.runtime_zip, args.packages_dir, args.output_dir, args.linux_runtime, args.linux_packages)))
