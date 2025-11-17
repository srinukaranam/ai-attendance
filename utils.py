from datetime import datetime, date, timezone, timedelta
import pytz

def get_local_time(utc_dt=None, timezone_str='Asia/Kolkata'):
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    local_tz = pytz.timezone(timezone_str)
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt

def format_local_date(utc_dt, format_str='%d %b %Y'):
    if utc_dt is None:
        return "N/A"

    # If it's a pure date (not datetime), don't call get_local_time()
    if isinstance(utc_dt, date) and not isinstance(utc_dt, datetime):
        return utc_dt.strftime(format_str)

    local_dt = get_local_time(utc_dt)
    return local_dt.strftime(format_str)

def format_local_time(utc_dt, format_str='%d %b %Y at %H:%M'):
    if utc_dt is None:
        return "N/A"
    local_dt = get_local_time(utc_dt)
    return local_dt.strftime(format_str)

def format_local_time_short(utc_dt, format_str='%H:%M'):
    if utc_dt is None:
        return "N/A"
    local_dt = get_local_time(utc_dt)
    return local_dt.strftime(format_str)
