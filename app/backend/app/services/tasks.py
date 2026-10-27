from uuid import UUID
import uuid
import sqlalchemy as sa
from fastapi import Request,HTTPException
from pydantic import Field
from backend.app.models import metadata as md
from backend.app.models.base import utcnow
from backend.app.schemas.common import PostingRouter
from backend.app.services.data import get
from backend.app.services.inventory import Input
from backend.app.services.workflows import perform
from backend.app.services.auth import audit

router=PostingRouter(prefix='/api/v1',tags=['Task assignments'])
class Assignees(Input):
    employee_ids:list[UUID]=Field(max_length=50)
    reason:str|None=Field(default=None,min_length=3,max_length=2000)

def replace_assignees(c,p,task_id,employee_ids,reason=None):
    task=get(c,'tasks',task_id,p,'tasks.write')
    if task['status'] in ('completed','cancelled'):raise HTTPException(409,'Công việc đã đóng')
    if task['created_by']!=p.user_id and not p.roles.intersection({'ADMIN','QC_LEADER'}):raise HTTPException(403,'Chỉ người giao việc hoặc quản lý được đổi người nhận')
    selected=[str(e) for e in employee_ids]
    if len(selected)!=len(set(selected)):raise HTTPException(422,'Nhân viên bị trùng')
    for eid in selected:
        employee=get(c,'employees',eid,p,'tasks.write')
        if employee['status']!='active':raise HTTPException(409,'Nhân viên đã ngừng hoạt động')
    table=md.tables['task_assignees'];rows=c.execute(sa.select(table).where(table.c.organization_id==p.organization_id,table.c.task_id==task_id)).mappings().all()
    existing={r['employee_id']:r for r in rows};now=utcnow()
    for eid,row in existing.items():
        if eid not in selected and row['status']!='removed':c.execute(table.update().where(table.c.id==row['id']).values(status='removed'))
    for eid in selected:
        old=existing.get(eid)
        if old and old['status']=='removed':c.execute(table.update().where(table.c.id==old['id']).values(status='assigned',assigned_at=now,assigned_by=p.user_id))
        elif not old:c.execute(table.insert().values(id=str(uuid.uuid4()),organization_id=p.organization_id,task_id=task_id,employee_id=eid,assigned_by=p.user_id,assigned_at=now))
    audit(c,p,'replace_assignees','tasks',task_id,{'employee_ids':selected,'reason':reason})
    return {'id':task_id,'employee_ids':selected}

@router.post('/tasks/{row_id}/assignees')
def assign(row_id:str,b:Assignees,request:Request):
    return perform(request,'tasks.write',b,lambda c,p,key:replace_assignees(c,p,row_id,b.employee_ids,b.reason))
