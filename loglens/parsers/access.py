"""M5 — combined-format parser for nginx/apache access logs."""

from __future__ import annotations

import re

from loglens.model import Record

_COMBINED_RE = re.compile(
    r'^(?P<client>\S+)\s+(?P<ident>\S+)\s+(?P<user>\S+)\s+'
    r'\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<agent>[^"]*)")?'
)

_STATUS_RE = re.compile(r"^(?P<status>\d{3})\s+(?P<bytes>\d+)$")


def _bytes_value(raw: str) -> int | None:
    if raw == "-":
        return 0
    if raw.isdigit():
        return int(raw)
    return None


def parse_access_line(line: str, source: str | None = None, line_no: int | None = None) -> Record:
    """Parse one combined/common access-log line into a Record.

    Falls back to raw text with no fields when the line does not match.
    """
    m = _COMBINED_RE.match(line)
    if not m:
        return Record(raw=line, message=line, source=source, line_no=line_no)
    parts = m.groupdict()
    fields: dict[str, object] = {
        "client": parts["client"],
        "ident": parts["ident"],
        "user": parts["user"],
        "method": parts["method"],
        "path": parts["path"],
        "protocol": parts["protocol"],
        "status": int(parts["status"]),
    }
    size = _bytes_value(parts["bytes"])
    if size is not None:
        fields["bytes"] = size
    if parts.get("referer") is not None:
        fields["referer"] = parts["referer"]
    if parts.get("agent") is not None:
        fields["agent"] = parts["agent"]
    message = f'{parts["method"]} {parts["path"]} -> {parts["status"]}'
    return Record(
        raw=line,
        message=message,
        fields=fields,
        source=source,
        line_no=line_no,
    )


def looks_like_access(line: str) -> bool:
    """Cheap heuristic: does this line look like an access-log entry?"""
    return _COMBINED_RE.match(line) is not None


def status_class(status: int) -> str:
    """Map an HTTP status to its 2xx/3xx/4xx/5xx class label."""
    if status < 300:
        return "2xx"
    if status < 400:
        return "3xx"
    if status < 500:
        return "4xx"
    return "5xx"
