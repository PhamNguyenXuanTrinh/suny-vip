from datetime import date,datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel
from backend.app.services.data import OUTPUTS

class ReportBase(BaseModel):
    generated_at:datetime
    source_tables:list[str]
class PagedReport(ReportBase):
    page:int
    page_size:int
class AgingItem(BaseModel):
    id:UUID
    party_id:UUID
    party_name:str
    reference:str
    due_date:date
    total_amount:int
    allocated_amount:int
    outstanding_amount:int
    overdue_days:int
    bucket:str
class AgingReport(PagedReport):
    items:list[AgingItem]
    total_items:int
    total_outstanding:int
    buckets:dict[str,int]
    as_of:date
    timezone:str
    currency:Literal['VND']
class InventoryItem(BaseModel):
    product_id:UUID
    warehouse_id:UUID
    uom:str
    quantity:str
    value_vnd:int
class InventoryReport(PagedReport):
    items:list[InventoryItem]
    total_groups:int
    on_hand_value_vnd:int
    in_transit_value_vnd:int
    total_value_vnd:int
    currency:Literal['VND']
    valuation:str
class ProductionItem(OUTPUTS['production_orders']):
    downtime_minutes:int
class UnitTotals(BaseModel):
    uom:str
    planned_quantity:str
    good_quantity:str
    scrap_quantity:str
class ProductionReport(PagedReport):
    items:list[ProductionItem]
    total_orders:int
    total_downtime_minutes:int
    totals_by_uom:list[UnitTotals]
class DashboardReport(ReportBase):
    revenue_vnd:int
    receivables_vnd:int
    payables_vnd:int
    inventory_value_vnd:int
    as_of:date
    currency:Literal['VND']
    definitions:dict[str,str]
class CashItem(BaseModel):
    date:date
    expected_receipts_vnd:int
    expected_payments_vnd:int
    net_vnd:int
class CashReport(ReportBase):
    items:list[CashItem]
    total_expected_net_vnd:int
    as_of:date
    currency:Literal['VND']
    opening_cash_balance:int|None
    note:str
class KPIItem(OUTPUTS['kpi_targets']):
    actual_value:str
    unit:str
    achieved:bool
    direction:Literal['at_most','at_least']
    source_tables:list[str]
    scope_note:str|None
class KPIReport(BaseModel):
    items:list[KPIItem]
    total_items:int
    page:int
    page_size:int
    generated_at:datetime
    source:str
