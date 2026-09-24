"""M8 — syslog parsing: RFC 3164 (BSD) and RFC 5424 formats."""

from __future__ import annotations

import re

from loglens.levels import SYSLOG_NUMBERS
from loglens.model import Record

# RFC 3164: Sep 19 10:07:21 myhost app[1234]: the message
_RFC3164_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+(?P<tag>[^\s:\[]+)(?:\[(?P<pid>\d+)\])?:\s?(?P<msg>.*)$"
)

# RFC 5424: <34>1 2026-09-19T10:07:21.123Z myhost app 1234 ID47 - the message
_RFC5424_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<version>\d)\s+"
    r"(?P<time>\S+)\s+(?P<host>\S+)\s+(?P<app>\S+)\s+(?P<pid>\S+)\s+(?P<msgid>\S+)\s+"
    r"(?P<structured>\S+)\s?(?P<msg>.*)$"
)

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

DEFAULT_YEAR = 2026


def parse_syslog_line(
    line: str,
    source: str | None = None,
    line_no: int | None = None,
    default_year: int | None = None,
) -> Record | None:
    """Parse a syslog line; ``None`` when it matches neither RFC shape."""
    if line.startswith("<"):
        return _parse_5424(line, source, line_no)
    return _parse_3164(line, source, line_no, default_year)


def _parse_3164(
    line: str,
    source: str | None,
    line_no: int | None,
    default_year: int | None,
) -> Record | None:
    m = _RFC3164_RE.match(line)
    if not m:
        return None
    parts = m.groupdict()
    month = _MONTHS.get(parts["month"])
    if month is None:
        return None
    year = default_year if default_year is not None else DEFAULT_YEAR
    from datetime import UTC, datetime

    hh, mm, ss = (int(x) for x in parts["time"].split(":"))
    timestamp = datetime(year, month, int(parts["day"]), hh, mm, ss, tzinfo=UTC)
    fields: dict[str, object] = {
        "host": parts["host"],
        "tag": parts["tag"],
        "facility": parts["tag"],
    }
    if parts["pid"]:
        fields["pid"] = int(parts["pid"])
    return Record(
        raw=line,
        message=parts["msg"],
        timestamp=timestamp,
        fields=fields,
        source=source,
        line_no=line_no,
    )


def _parse_5424(line: str, source: str | None, line_no: int | None) -> Record | None:
    m = _RFC5424_RE.match(line)
    if not m:
        return None
    parts = m.groupdict()
    pri = int(parts["pri"])
    severity = pri % 8
    facility_code = pri // 8
    from loglens.timestamps import TimestampParser

    timestamp = TimestampParser().parse(parts["time"])
    fields: dict[str, object] = {
        "host": parts["host"],
        "app": parts["app"],
        "tag": parts["app"],
        "msgid": parts["msgid"],
        "facility_code": facility_code,
        "severity_code": severity,
    }
    if parts["pid"].isdigit():
        fields["pid"] = int(parts["pid"])
    if parts["structured"] != "-":
        fields["structured_data"] = parts["structured"]
    return Record(
        raw=line,
        message=parts["msg"],
        timestamp=timestamp,
        level=SYSLOG_NUMBERS.get(severity),
        fields=fields,
        source=source,
        line_no=line_no,
    )


def looks_like_syslog(line: str) -> bool:
    if line.startswith("<"):
        return _RFC5424_RE.match(line) is not None
    m = _RFC3164_RE.match(line)
    if not m:
        return False
    return m.group("month") in _MONTHS


def facility_name(code: int) -> str:
    """RFC 5424 facility codes to readable names (common subset)."""
    names = {
        0: "kernel", 1: "user", 2: "mail", 3: "daemon", 4: "auth",
        5: "syslog", 6: "lpr", 7: "news", 8: "uucp", 9: "clock",
        10: "authpriv", 11: "ftp", 12: "ntp", 13: "audit", 14: "alert",
        15: "clock2", 16: "local0", 17: "local1", 18: "local2", 19: "local3",
        20: "local4", 21: "local5", 22: "local6", 23: "local7",
    }
    return names.get(code, f"facility{code}")
