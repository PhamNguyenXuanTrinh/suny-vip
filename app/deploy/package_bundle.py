"""Package only verified bundle-manifest entries; preserve executable permissions."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,json,os,tempfile,zipfile

def package(stage,output):
    stage=Path(stage).resolve();output=Path(output).resolve()
    manifest=json.loads((stage/'BUNDLE_SHA256.json').read_text())
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for name,expected in sorted(manifest['files'].items()):
            relative=PurePosixPath(name);path=stage/name
            if relative.is_absolute() or '..' in relative.parts or '\\' in name or path.is_symlink() or not path.resolve().is_relative_to(stage):raise ValueError('Unsafe bundle path')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Bundle changed before packaging: '+name)
            info=zipfile.ZipInfo.from_file(path,'SUNNY_ERP/'+name)
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        archive.write(stage/'BUNDLE_SHA256.json','SUNNY_ERP/BUNDLE_SHA256.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.sunny-package-',dir=output.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(buffer.getvalue());f.flush();os.fsync(f.fileno())
        os.replace(temp,output)
    finally:Path(temp).unlink(missing_ok=True)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise ValueError('Archive CRC verification failed')
        total=sum(i.file_size for i in archive.infolist());files=len(archive.infolist())
    return {'file':str(output),'bytes':output.stat().st_size,'uncompressed_bytes':total,'files':files,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(package(args.stage,args.output),ensure_ascii=False))
