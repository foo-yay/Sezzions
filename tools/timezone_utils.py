"""
Timezone utilities for UTC storage + local display.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, available_timezones


def get_system_timezone_name() -> str:
    """Best-effort system timezone name (IANA)."""
    try:
        tzinfo = datetime.now().astimezone().tzinfo
        if tzinfo is not None and hasattr(tzinfo, "key"):
            return tzinfo.key
    except Exception:
        pass
    return "UTC"


def _get_settings_value(settings: Optional[object], key: str, default=None):
    if settings is None:
        return default
    getter = getattr(settings, "get", None)
    if callable(getter):
        return settings.get(key, default)
    return default


def get_accounting_timezone_name(settings: Optional[object] = None) -> str:
    """Return Accounting (Home/Tax) timezone name or system default."""
    value = _get_settings_value(settings, "accounting_time_zone", None)
    if value:
        return str(value)
    value = _get_settings_value(settings, "time_zone", None)
    if value:
        return str(value)
    try:
        from ui.settings import Settings

        stored = Settings().get("accounting_time_zone", None)
        if stored:
            return str(stored)
        stored = Settings().get("time_zone", None)
        if stored:
            return str(stored)
    except Exception:
        pass
    return get_system_timezone_name()


def get_entry_timezone_name(settings: Optional[object] = None) -> str:
    """Return Entry/Current timezone name (travel-aware)."""
    travel_enabled = bool(_get_settings_value(settings, "travel_mode_enabled", False))
    if travel_enabled:
        current_tz = _get_settings_value(settings, "current_time_zone", None)
        if current_tz:
            return str(current_tz)
    return get_accounting_timezone_name(settings)


def get_configured_timezone_name(settings: Optional[object] = None) -> str:
    """Backward-compatible alias for Accounting timezone."""
    return get_accounting_timezone_name(settings)


def get_timezone(tz_name: Optional[str] = None) -> ZoneInfo:
    """Return ZoneInfo for a timezone name with UTC fallback."""
    tz_key = tz_name or get_system_timezone_name()
    try:
        return ZoneInfo(tz_key)
    except Exception:
        return ZoneInfo("UTC")


def list_timezones() -> list[str]:
    """Return sorted IANA timezone names."""
    return sorted(available_timezones())


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _normalize_time_value(value: Optional[str]) -> str:
    if not value:
        return "00:00:00"
    value = value.strip()
    if len(value) == 5:
        return f"{value}:00"
    return value


def local_date_time_to_utc(
    local_date: date | str,
    local_time: Optional[str],
    tz_name: Optional[str] = None,
) -> Tuple[str, str]:
    """Convert local date/time to UTC date/time strings (YYYY-MM-DD, HH:MM:SS)."""
    tz = get_timezone(tz_name)
    date_value = _parse_date(local_date)
    time_str = _normalize_time_value(local_time)
    naive = datetime.combine(date_value, datetime.strptime(time_str, "%H:%M:%S").time())
    aware = naive.replace(tzinfo=tz)
    utc_dt = aware.astimezone(timezone.utc)
    return utc_dt.date().isoformat(), utc_dt.strftime("%H:%M:%S")


def local_date_time_to_utc_entry(
    local_date: date | str,
    local_time: Optional[str],
    settings: Optional[object] = None,
) -> Tuple[str, str]:
    """Convert Entry-local date/time to UTC using current Entry TZ."""
    tz_name = get_entry_timezone_name(settings)
    return local_date_time_to_utc(local_date, local_time, tz_name)


def utc_date_time_to_local(
    utc_date: date | str,
    utc_time: Optional[str],
    tz_name: Optional[str] = None,
) -> Tuple[date, str]:
    """Convert UTC date/time strings to local date/time."""
    tz = get_timezone(tz_name)
    date_value = _parse_date(utc_date)
    time_str = _normalize_time_value(utc_time)
    naive = datetime.combine(date_value, datetime.strptime(time_str, "%H:%M:%S").time())
    aware = naive.replace(tzinfo=timezone.utc)
    local_dt = aware.astimezone(tz)
    return local_dt.date(), local_dt.strftime("%H:%M:%S")


def local_date_range_to_utc_bounds(
    start_date: date,
    end_date: date,
    tz_name: Optional[str] = None,
) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """Convert a local date range to UTC date/time bounds (start/end inclusive)."""
    start_dt = local_date_time_to_utc(start_date, "00:00:00", tz_name)
    end_dt = local_date_time_to_utc(end_date, "23:59:59", tz_name)
    return start_dt, end_dt


def get_accounting_timezone_for_utc(
    db,
    utc_date: date | str,
    utc_time: Optional[str],
    settings: Optional[object] = None,
) -> str:
    """Return Accounting TZ in effect at a given UTC date/time."""
    if db is None:
        return get_accounting_timezone_name(settings)
    try:
        utc_date_str = _parse_date(utc_date).isoformat()
        time_str = _normalize_time_value(utc_time)
        utc_timestamp = f"{utc_date_str} {time_str}"
        row = db.fetch_one(
            """
            SELECT accounting_time_zone
            FROM accounting_time_zone_history
            WHERE effective_utc_timestamp <= ?
            ORDER BY effective_utc_timestamp DESC
            LIMIT 1
            """,
            (utc_timestamp,),
        )
        if row and row.get("accounting_time_zone"):
            return str(row["accounting_time_zone"])
    except Exception:
        pass
    return get_accounting_timezone_name(settings)


def utc_date_time_to_accounting_local(
    db,
    utc_date: date | str,
    utc_time: Optional[str],
    settings: Optional[object] = None,
) -> Tuple[date, str]:
    """Convert UTC date/time to Accounting-local date/time using history."""
    tz_name = get_accounting_timezone_for_utc(db, utc_date, utc_time, settings)
    return utc_date_time_to_local(utc_date, utc_time, tz_name)


def utc_timestamp_to_local(timestamp: str, tz_name: Optional[str] = None) -> datetime:
    """Convert a UTC timestamp string to local datetime."""
    tz = get_timezone(tz_name)
    ts = timestamp.strip()
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        parsed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(tz)


def local_datetime_to_utc_timestamp(
    local_date: date | str,
    local_time: Optional[str],
    tz_name: Optional[str] = None,
) -> str:
    """Convert local date/time to UTC timestamp string (YYYY-MM-DD HH:MM:SS)."""
    utc_date_str, utc_time_str = local_date_time_to_utc(local_date, local_time, tz_name)
    return f"{utc_date_str} {utc_time_str}"
