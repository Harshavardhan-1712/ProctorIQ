"""
utils/formatting.py
---------------------
Display-formatting helpers. Kept separate from utils/validators.py
since these are output-formatting concerns, not input validation.

Why this file exists: `User.created_at` is stored as a naive UTC
datetime (`datetime.utcnow()` in models/user.py — this is deliberate,
storing UTC in the database is the correct practice). The dashboard
was previously rendering that raw UTC value with a plain `strftime`
call, which LOOKS formatted but is actually the wrong wall-clock time
for any candidate not in the UTC timezone — e.g. a candidate in India
(UTC+5:30) would see a registration time 5.5 hours in the past. This
module fixes that by converting to a configured display timezone
before formatting.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Default display timezone if the app config doesn't specify one.
# India Standard Time, matching this project's primary user base.
DEFAULT_DISPLAY_TIMEZONE = "Asia/Kolkata"

DEFAULT_FORMAT = "%d %b %Y, %I:%M %p"


def format_local_datetime(
    dt_utc: datetime | None,
    tz_name: str = DEFAULT_DISPLAY_TIMEZONE,
    fmt: str = DEFAULT_FORMAT,
) -> str:
    """
    Convert a naive UTC datetime (as stored by SQLAlchemy via
    `datetime.utcnow()`) into a human-readable string in `tz_name`.

    Returns an empty string for `None` so templates can call this on
    optional fields without needing a separate null-check.
    """
    if dt_utc is None:
        return ""

    # The datetime from the DB is naive (no tzinfo) but represents UTC.
    # Attach UTC tzinfo explicitly before converting, otherwise
    # `.astimezone()` would incorrectly assume it's already in local time.
    aware_utc = dt_utc.replace(tzinfo=timezone.utc)
    local_dt = aware_utc.astimezone(ZoneInfo(tz_name))

    tz_label = tz_name.split("/")[-1].replace("_", " ")
    return f"{local_dt.strftime(fmt)} ({tz_label})"
