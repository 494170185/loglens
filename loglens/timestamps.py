"""M4 — timestamp parsing across the formats logs actually use."""

from __future__ import annotations

import re
from datetime import UTC, datetime

_STRPTIME_FORMATS = (
    # ISO-ish variants that fromisoformat cannot handle on all versions.
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    # Nginx / Apache access log: 19/Sep/2026:10:07:21 +0000
    "%d/%b/%Y:%H:%M:%S %z",
    # Apache error log: Sun Sep 20 04:05:06.789123 2026
    "%a %b %d %H:%M:%S.%f %Y",
    "%a %b %d %H:%M:%S %Y",
    # Old-style syslog / RFC 3164: Sep 19 10:07:21
    "%b %d %H:%M:%S",
    "%b %d %H:%M:%S,%f",
    # Go stack traces / some Java logs: 2026/09/19 10:07:21
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S.%f",
    # Java log4j/slf4j classic: 2026-09-19 10:07:21,123
    "%Y-%m-%d %H:%M:%S,%f%z",
    # Condensed machine-readable: 20260919T100721Z
    "%Y%m%dT%H:%M:%S%z",
    # Heroku-style with milliseconds offset: 2026-09-19T10:07:21.123+00:00
    "%Y-%m-%dT%H:%M:%S.%f",
)

_EPOCH_RE = re.compile(r"^(\d{10})(?:\.(\d{1,6}))?$")
_MILLIS_RE = re.compile(r"^(\d{13})$")

# Current year injected into year-less syslog timestamps so that
# "Sep 19 10:07:21" becomes a full datetime.
_DEFAULT_YEAR: int | None = None


def set_default_year(year: int | None) -> None:
    """Pin the year used for year-less formats (tests and reproducible runs)."""
    global _DEFAULT_YEAR
    _DEFAULT_YEAR = year


class TimestampParser:
    """Parse the timestamp dialects found in access logs, syslog and app logs."""

    def __init__(self, default_year: int | None = None):
        self.default_year = default_year

    def parse(self, text: str) -> datetime | None:
        """Parse *text* to a timezone-aware datetime, or None.

        Naive results are normalized to UTC; aware results keep their offset.
        """
        if not text:
            return None
        text = text.strip().strip("[]")
        if not text:
            return None
        dt = self._try_iso(text)
        if dt is None:
            dt = self._try_epoch(text)
        if dt is None:
            dt = self._try_formats(text)
        if dt is None:
            return None
        return _normalize(dt)

    # -- individual strategies ------------------------------------------------

    def _try_iso(self, text: str) -> datetime | None:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _try_epoch(self, text: str) -> datetime | None:
        m = _EPOCH_RE.match(text)
        if m:
            micro = int((m.group(2) or "").ljust(6, "0"))
            return datetime.fromtimestamp(int(m.group(1)), tz=UTC).replace(
                microsecond=micro
            )
        m = _MILLIS_RE.match(text)
        if m:
            return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=UTC)
        return None

    def _try_formats(self, text: str) -> datetime | None:
        for fmt in _STRPTIME_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
            except ValueError:
                continue
            if dt.tzinfo is None and dt.year == 1900:
                # Year-less format (RFC 3164): stamp it with the current or
                # caller-pinned year so it compares against real timestamps.
                dt = dt.replace(year=self._effective_default_year())
            return dt
        return None

    def _effective_default_year(self) -> int:
        if self.default_year is not None:
            return self.default_year
        if _DEFAULT_YEAR is not None:
            return _DEFAULT_YEAR
        return datetime.now(tz=UTC).year


def _normalize(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def to_utc(dt: datetime) -> datetime:
    """Convert an aware datetime to UTC (naive input assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_timestamp(dt: datetime, style: str = "iso") -> str:
    """Render a datetime for reports: ``iso`` or ``access`` (nginx style)."""
    dt = to_utc(dt)
    if style == "access":
        return dt.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def clamp_year(dt: datetime, floor: int, ceiling: int) -> datetime:
    """Guard against two-digit-year and epoch-parsing absurdities."""
    if dt.year < floor:
        return dt.replace(year=floor)
    if dt.year > ceiling:
        return dt.replace(year=ceiling)
    return dt


def gap_seconds(a: datetime, b: datetime) -> float:
    """Signed seconds between two datetimes (a - b), both treated as UTC."""
    delta = to_utc(a) - to_utc(b)
    return delta.total_seconds()


def round_to_bucket(dt: datetime, seconds: int) -> datetime:
    """Floor a datetime to the start of its *seconds* bucket."""
    dt = to_utc(dt)
    epoch_seconds = int(dt.timestamp())
    return datetime.fromtimestamp(epoch_seconds - epoch_seconds % seconds, tz=UTC)
