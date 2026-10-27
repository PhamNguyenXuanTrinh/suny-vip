"""Verify the delivered source files against CURRENT_SHA256.json."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
manifest=ROOT/'CURRENT_SHA256.json'
if not manifest.is_file():raise SystemExit('Missing CURRENT_SHA256.json')
data=json.loads(manifest.read_text(encoding='utf-8'))
errors=[]
for relative,expected in data['files'].items():
    path=(ROOT/relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file() or path.is_symlink():
        errors.append(relative+': missing or invalid path');continue
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append(relative+': hash mismatch')
if errors:
    print(json.dumps({'verified':False,'errors':errors},ensure_ascii=False,indent=2));raise SystemExit(1)
print(json.dumps({'verified':True,'files':len(data['files']),'application':data['application']}))
