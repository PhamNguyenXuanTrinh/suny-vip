from pathlib import Path
import hashlib,io,uuid
import sqlalchemy as sa
from fastapi import APIRouter,Request,UploadFile,File,HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from pypdf import PdfReader
from backend.app.models import metadata as md
from backend.app.core.security import current
from backend.app.services.data import serialize
from backend.app.services.auth import audit

router=APIRouter(prefix='/api/v1/documents',tags=['Private document attachments'])

@router.post('',status_code=201)
@router.post('/upload',status_code=201)
async def upload(request:Request,file:UploadFile=File(...)):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('documents.write')
    data=await file.read(10_000_001)
    if not data or len(data)>10_000_000:raise HTTPException(413,'Dung lượng tệp cần từ 1 byte đến 10 MB')
    media=file.content_type;ext={'image/jpeg':'.jpg','image/png':'.png','application/pdf':'.pdf'}.get(media)
    if not ext:raise HTTPException(415,'Chỉ nhận ảnh JPEG, PNG hoặc PDF')
    try:
        if media=='application/pdf':
            doc=PdfReader(io.BytesIO(data),strict=True)
            if doc.is_encrypted or not 1<=len(doc.pages)<=100:raise ValueError('PDF invalid')
        else:
            with Image.open(io.BytesIO(data)) as image:
                if image.format!=('JPEG' if media=='image/jpeg' else 'PNG') or image.width*image.height>40_000_000:raise ValueError('Image mismatch')
                image.verify()
    except Exception:raise HTTPException(415,'Nội dung tệp không khớp định dạng khai báo')
    rid=str(uuid.uuid4());key=uuid.uuid4().hex+ext;folder=request.app.state.settings.upload_path.resolve();folder.mkdir(parents=True,exist_ok=True);target=folder/key
    try:
        with request.app.state.engine.begin() as c:
            p=current(c,request);p.require('documents.write')
            target.write_bytes(data);target.chmod(0o600)
            c.execute(md.tables['documents'].insert().values(id=rid,organization_id=p.organization_id,original_name=Path(file.filename or 'document').name[:255],media_type=media,byte_size=len(data),storage_key=key,sha256=hashlib.sha256(data).hexdigest(),uploaded_by=p.user_id,source_kind='general'))
            audit(c,p,'upload','documents',rid,{'byte_size':len(data),'media_type':media})
    except Exception:
        target.unlink(missing_ok=True);raise
    return {'id':rid,'original_name':Path(file.filename or 'document').name[:255],'byte_size':len(data)}

@router.get('')
def listing(request:Request,page:int=1,page_size:int=25):
    if page<1 or not 1<=page_size<=100:raise HTTPException(422,'Phân trang không hợp lệ')
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('documents.write');t=md.tables['documents'];where=[t.c.organization_id==p.organization_id]
        if not p.is_global_admin:where.append(t.c.uploaded_by==p.user_id)
        rows=c.execute(sa.select(t).where(*where).order_by(t.c.created_at.desc()).offset((page-1)*page_size).limit(page_size)).mappings()
        return {'items':[{k:v for k,v in serialize(r).items() if k!='storage_key'} for r in rows],'total':c.execute(sa.select(sa.func.count()).select_from(t).where(*where)).scalar_one()}

@router.get('/{row_id}/download')
def download(row_id:str,request:Request):
    with request.app.state.engine.begin() as c:
        p=current(c,request);p.require('documents.write');t=md.tables['documents']
        conditions=[t.c.id==row_id,t.c.organization_id==p.organization_id]
        if not p.is_global_admin:conditions.append(t.c.uploaded_by==p.user_id)
        r=c.execute(sa.select(t).where(*conditions)).mappings().first()
        if not r:raise HTTPException(404,'Không tìm thấy tài liệu')
        folder=request.app.state.settings.upload_path.resolve();target=(folder/r['storage_key']).resolve()
        if not target.is_relative_to(folder) or not target.is_file():raise HTTPException(404,'Không tìm thấy tệp')
        return FileResponse(target,media_type=r['media_type'],filename=r['original_name'],content_disposition_type='attachment')
