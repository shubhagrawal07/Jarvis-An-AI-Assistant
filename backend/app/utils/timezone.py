from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def get_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def local_date_at(dt: datetime | None, tz_name: str) -> date:
    if dt is None:
        dt = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(get_zone(tz_name)).date()


def local_day_bounds_utc(local_d: date, tz_name: str) -> tuple[datetime, datetime]:
    """Return [start, end) UTC datetimes for the user's local calendar day."""
    z = get_zone(tz_name)
    start_local = datetime.combine(local_d, time.min, tzinfo=z)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)
