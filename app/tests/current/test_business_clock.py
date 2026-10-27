from datetime import date, datetime, timezone
import pytest
from backend.app.core.clock import business_today, day_start_utc
from backend.app.core.config import Settings
from .test_business import post
from .test_inventory import action


def test_business_day_is_local_while_stored_boundaries_are_utc(monkeypatch):
    monkeypatch.setenv('SUNNY_BUSINESS_TIMEZONE', 'Asia/Ho_Chi_Minh')
    assert business_today(datetime(2026,10,25,17,0,tzinfo=timezone.utc)) == date(2026,10,26)
    assert day_start_utc(date(2026,10,26)) == datetime(2026,10,25,17,0,tzinfo=timezone.utc)
    monkeypatch.setenv('SUNNY_BUSINESS_TIMEZONE', 'UTC')
    assert business_today(datetime(2026,10,25,17,0,tzinfo=timezone.utc)) == date(2026,10,25)


def test_revenue_uses_current_business_date_not_utc_date(erp, monkeypatch):
    from backend.app.services import reports
    monkeypatch.setenv('SUNNY_BUSINESS_TIMEZONE', 'Asia/Ho_Chi_Minh')
    monkeypatch.setattr(reports, 'utcnow', lambda: datetime(2026,10,25,18,0,tzinfo=timezone.utc))
    c, login, *_ = erp
    h = login()
    customer = post(c,h,'customers',{'customer_code':'LOCAL-DAY','name':'Ngày kinh doanh'})
    for day, amount, code in [('2026-10-26',1000,'TODAY'),('2026-10-27',2000,'FUTURE')]:
        invoice = post(c,h,'customer-invoices',{'invoice_no':code,'customer_id':customer['id'],'invoice_date':day,'lines':[{'line_no':1,'quantity':'1','uom':'m2','unit_price':amount}]})
        assert action(c,h,'customer-invoices/'+invoice['id']+'/issue').status_code == 200
    report = c.get('/api/v1/reports/dashboard-money',headers=h).json()
    assert report['as_of']=='2026-10-26' and report['revenue_vnd']==1000


def test_ar_close_excludes_payments_after_local_midnight(erp, monkeypatch):
    from backend.app.services import finance
    monkeypatch.setenv('SUNNY_BUSINESS_TIMEZONE', 'Asia/Ho_Chi_Minh')
    c,login,*_=erp
    h=login()
    customer=post(c,h,'customers',{'customer_code':'CUTOFF','name':'Chốt ngày'})
    invoice=post(c,h,'customer-invoices',{'invoice_no':'CUT','customer_id':customer['id'],'invoice_date':'2026-10-26','lines':[{'line_no':1,'quantity':'1','uom':'m2','unit_price':1000}]})
    assert action(c,h,'customer-invoices/'+invoice['id']+'/issue').status_code==200
    receipt=post(c,h,'customer-receipts',{'receipt_code':'PAY-NEXT-DAY','customer_id':customer['id'],'amount':1000,'payment_method':'cash'})
    assert action(c,h,'customer-receipts/'+receipt['id']+'/verify').status_code==200
    # 17:00 UTC is 00:00 on the following Vietnam business day.
    monkeypatch.setattr(finance,'utcnow',lambda:datetime(2026,10,26,17,0,tzinfo=timezone.utc))
    assert action(c,h,'customer-receipts/'+receipt['id']+'/allocations',{'invoice_id':invoice['id'],'amount':1000}).status_code==200
    prior=c.get('/api/v1/reports/ar-aging?as_of=2026-10-26',headers=h).json()
    after=c.get('/api/v1/reports/ar-aging?as_of=2026-10-27',headers=h).json()
    assert prior['total_outstanding']==1000 and after['total_outstanding']==0
    assert prior['timezone']=='Asia/Ho_Chi_Minh'


def test_invalid_business_timezone_does_not_silently_use_utc(monkeypatch):
    monkeypatch.setenv('SUNNY_JWT_SECRET','a'*48)
    monkeypatch.setenv('SUNNY_BUSINESS_TIMEZONE','Invalid/Zone')
    with pytest.raises(RuntimeError,match='TIMEZONE'):
        Settings.from_env()
