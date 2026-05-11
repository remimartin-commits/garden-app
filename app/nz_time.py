"""New Zealand local time helpers (Pacific/Auckland).

SQLite columns store **naive datetimes as NZ wall-clock** times (what you would read
off a clock in Auckland). Browser ``datetime-local`` values without a zone are
interpreted the same way. ISO strings returned from APIs use an explicit offset
(+12/+13) so clients can display correctly.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

NZ = ZoneInfo("Pacific/Auckland")


def nz_naive_now() -> datetime:
    """Current NZ local time as naive datetime (for ORM defaults)."""
    return datetime.now(NZ).replace(tzinfo=None)


def nz_today() -> date:
    """Current calendar date in New Zealand."""
    return datetime.now(NZ).date()


def parse_iso_to_naive_nz_wall(raw: str | None) -> datetime | None:
    """Parse ISO input; aware values are converted to NZ wall clock; result is naive."""
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(microsecond=0)
    return dt.astimezone(NZ).replace(tzinfo=None, microsecond=0)


def parse_any_to_naive_nz_wall(raw: Any) -> datetime | None:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return None
    return parse_iso_to_naive_nz_wall(str(raw))


def nz_wall_naive_to_iso_with_offset(dt: datetime | None) -> str | None:
    """Serialize naive NZ wall time to ISO-8601 with Pacific/Auckland offset."""
    if dt is None:
        return None
    aware = dt.replace(tzinfo=NZ) if dt.tzinfo is None else dt.astimezone(NZ)
    return aware.replace(microsecond=0).isoformat()


def nz_calendar_date_from_stored(dt: datetime | None) -> date | None:
    """Calendar date in NZ for a stored job time (naive = NZ wall)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(NZ).date()
