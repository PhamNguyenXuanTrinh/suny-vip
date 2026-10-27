from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,Header
from fastapi.datastructures import DefaultPlaceholder
from pydantic import BaseModel,ConfigDict

class FieldError(BaseModel):
    field:str
    message:str
class ErrorDetail(BaseModel):
    code:str
    message:str
    request_id:UUID|None=None
    fields:list[FieldError]|None=None
class ErrorEnvelope(BaseModel):error:ErrorDetail
class PostingResult(BaseModel):
    model_config=ConfigDict(extra='allow')
    id:UUID|None=None
    status:str|None=None
    movement_id:UUID|None=None
    inventory_unit_id:UUID|None=None
    remaining_quantity:str|None=None
    invoice_remaining:int|None=None
    payment_remaining:int|None=None

def posting_key(key:Annotated[str,Header(alias='Idempotency-Key',min_length=8,max_length=120)]):return key

class PostingRouter(APIRouter):
    def add_api_route(self,path,endpoint,**kwargs):
        if 'POST' in (kwargs.get('methods') or []):
            kwargs['dependencies']=[*(kwargs.get('dependencies') or []),Depends(posting_key)]
            kwargs.setdefault('response_model',PostingResult)
            if kwargs['response_model'] is None or isinstance(kwargs['response_model'],DefaultPlaceholder):kwargs['response_model']=PostingResult
            kwargs['response_model_exclude_none']=True
        return super().add_api_route(path,endpoint,**kwargs)
