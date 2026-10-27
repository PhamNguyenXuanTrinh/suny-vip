"""UTC storage, explicitly configured local business dates."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import os


def business_zone():
    return ZoneInfo(os.getenv('SUNNY_BUSINESS_TIMEZONE', 'Asia/Ho_Chi_Minh'))


def business_today(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(business_zone()).date()


def day_start_utc(day):
    return datetime.combine(day, time.min, tzinfo=business_zone()).astimezone(timezone.utc)
