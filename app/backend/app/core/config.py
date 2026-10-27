from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import os, json

ROOT = Path(__file__).resolve().parents[3]

@dataclass(frozen=True)
class Settings:
    database_path: str
    jwt_secret: str
    upload_path: Path
    access_seconds: int = 900
    refresh_seconds: int = 604800
    max_sessions: int = 8
    origins: tuple[str, ...] = ('http://127.0.0.1:8765',)

    @classmethod
    def from_env(cls):
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, values):
        secret = values.get('SUNNY_JWT_SECRET', '')
        if len(secret) < 32:
            raise RuntimeError('SUNNY_JWT_SECRET must contain at least 32 characters; run the local setup command')
        try:
            cap = int(values.get('SUNNY_MAX_SESSIONS', '8'))
            interval = int(values.get('SUNNY_ALERT_INTERVAL_SECONDS', '300'))
            if not 1 <= cap <= 100 or not 30 <= interval <= 86400:
                raise ValueError()
        except ValueError:
            raise RuntimeError('SUNNY_MAX_SESSIONS cần 1–100; khoảng cảnh báo cần 30–86400 giây') from None
        try:
            ZoneInfo(values.get('SUNNY_BUSINESS_TIMEZONE', 'Asia/Ho_Chi_Minh'))
        except (ValueError, ZoneInfoNotFoundError):
            raise RuntimeError('SUNNY_BUSINESS_TIMEZONE không hợp lệ hoặc thiếu dữ liệu múi giờ') from None
        try:
            thresholds = json.loads(values.get('SUNNY_RECEIPT_SPIKE_THRESHOLDS', '{}'))
            if not isinstance(thresholds, dict):
                raise ValueError()
            for value in thresholds.values():
                if not isinstance(value, dict):
                    raise ValueError()
                for key in ('minimum_quantity', 'factor'):
                    if key in value and (not Decimal(str(value[key])).is_finite() or Decimal(str(value[key])) < 0):
                        raise ValueError()
                if 'baseline_days' in value and (type(value['baseline_days']) is not int or not 1 <= value['baseline_days'] <= 365):
                    raise ValueError()
        except (ValueError, TypeError, InvalidOperation):
            raise RuntimeError('Ngưỡng cảnh báo không hợp lệ') from None

        db_config = values.get('SUNNY_ERP_DB', str(ROOT / 'runtime/database/sunny.sqlite3'))
        
        # Tự động nhận diện link Postgres và đổi thành postgresql://
        if db_config.startswith('postgres://'):
            db_config = db_config.replace('postgres://', 'postgresql://', 1)

        return cls(
            database_path=db_config,
            jwt_secret=secret,
            upload_path=Path(values.get('SUNNY_UPLOAD_DIR', ROOT / 'runtime/uploads')),
            max_sessions=cap,
            origins=tuple(x for x in values.get('SUNNY_ALLOWED_ORIGINS', 'http://127.0.0.1:8765').split(',') if x)
        )