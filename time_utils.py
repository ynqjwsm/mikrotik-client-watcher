import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

from settings import settings


def get_timezone() -> Union[timezone, 'zoneinfo.ZoneInfo', 'pytz.BaseTzInfo']:
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(settings.timezone)
    except Exception:
        pass
    
    try:
        import pytz
        return pytz.timezone(settings.timezone)
    except Exception:
        pass
    
    return timezone.utc


def now() -> datetime:
    tz = get_timezone()
    return datetime.now(tz=tz)


def localize(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        tz = get_timezone()
        if hasattr(tz, 'localize'):
            return tz.localize(dt)
        return dt.replace(tzinfo=tz)
    return dt


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    tz = get_timezone()
    
    if dt.tzinfo is None:
        dt_local = localize(dt)
    else:
        try:
            dt_local = dt.astimezone(tz)
        except Exception:
            dt_local = dt
    
    return dt_local.strftime(fmt)


def set_os_timezone() -> None:
    os.environ["TZ"] = settings.timezone
    try:
        import time
        time.tzset()
    except AttributeError:
        pass
