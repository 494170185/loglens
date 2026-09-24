"""M7 — logfmt (key=value) parser."""

from __future__ import annotations

import re

from loglens.model import Record

_PAIR_RE = re.compile(
    r'(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)='
    r'(?P<value>"(?:[^"\\]|\\.)*"|\'[^\']*\'|\S+)'
)

_LEVEL_KEYS = ("level", "lvl", "severity")
_MESSAGE_KEYS = ("msg", "message")
_TIME_KEYS = ("time", "ts", "timestamp")


def parse_logfmt_line(
    line: str,
    source: str | None = None,
    line_no: int | None = None,
) -> Record | None:
    """Parse a ``key=value`` line; ``None`` when no pairs are found."""
    pairs = _PAIR_RE.findall(line)
    if not pairs:
        return None
    fields: dict[str, object] = {}
    for key, raw in pairs:
        fields[key] = _coerce(_unquote(raw))
    from loglens.levels import normalize_level
    from loglens.timestamps import TimestampParser

    level = None
    for key in _LEVEL_KEYS:
        if key in fields:
            level = normalize_level(fields[key])  # type: ignore[arg-type]
            if level:
                break
    timestamp = None
    for key in _TIME_KEYS:
        if key in fields and isinstance(fields[key], str):
            timestamp = TimestampParser().parse(fields[key])
            if timestamp:
                break
    message = ""
    for key in _MESSAGE_KEYS:
        if key in fields and isinstance(fields[key], str) and fields[key]:
            message = fields[key]
            break
    return Record(
        raw=line,
        message=message,
        timestamp=timestamp,
        level=level,
        fields=fields,
        source=source,
        line_no=line_no,
    )


def _unquote(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        body = raw[1:-1]
        if raw[0] == '"':
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        return body
    return raw


def _coerce(text: str) -> object:
    if text == "-":
        return ""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null" or text == "":
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def looks_like_logfmt(line: str) -> bool:
    """At least two key=value pairs, or one pair plus other tokens."""
    pairs = _PAIR_RE.findall(line)
    if len(pairs) >= 2:
        return True
    if len(pairs) == 1:
        return bool(line.strip())
    return False
