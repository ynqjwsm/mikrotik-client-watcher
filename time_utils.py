import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from settings import settings


def get_timezone() -> timezone:
    try:
        if hasattr(datetime, "astimezone"):
            import zoneinfo
            tz = zoneinfo.ZoneInfo(settings.timezone)
            return timezone(timedelta(seconds=tz.utcoffset(datetime.now())), settings.timezone)
    except Exception:
        pass
    
    try:
        import pytz
        tz = pytz.timezone(settings.timezone)
        return timezone(timedelta(seconds=tz.utcoffset(datetime.now())), settings.timezone)
    except Exception:
        pass
    
    return timezone.utc


def now() -> datetime:
    tz = get_timezone()
    return datetime.now(tz=tz)


def localize(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        tz = get_timezone()
        return dt.replace(tzinfo=tz)
    return dt


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    dt_local = localize(dt)
    return dt_local.strftime(fmt)


def set_os_timezone() -> None:
    os.environ["TZ"] = settings.timezone
    try:
        import time
        time.tzset()
    except AttributeError:
        pass
