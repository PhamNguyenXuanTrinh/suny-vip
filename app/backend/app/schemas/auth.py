from pydantic import BaseModel,ConfigDict,Field
from uuid import UUID

class Input(BaseModel):model_config=ConfigDict(extra='forbid')
class Login(Input):
    username:str=Field(min_length=1,max_length=120)
    password:str=Field(min_length=1,max_length=128)
class Refresh(Input):refresh_token:str=Field(min_length=32,max_length=256)
class PasswordChange(Input):
    current_password:str=Field(max_length=128)
    new_password:str=Field(min_length=12,max_length=128)
class UserCreate(Input):
    employee_id:UUID
    username:str=Field(min_length=3,max_length=120,pattern=r'^[a-z0-9][a-z0-9_.-]+$')
    password:str=Field(min_length=12,max_length=128)
class UserEdit(Input):
    is_active:bool|None=None
    new_password:str|None=Field(default=None,min_length=12,max_length=128)
class RoleGrant(Input):
    code:str=Field(pattern='^(ADMIN|SALES|CTV|ACCOUNTANT|QC_LEADER|WORKER)$')
    site_id:UUID|None=None
class Grants(Input):grants:list[RoleGrant]=Field(max_length=20)
