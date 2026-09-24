"""M6 — JSON Lines parser producing structured records."""

from __future__ import annotations

import json
from typing import Any

from loglens.model import Record

_TIMESTAMP_KEYS = ("timestamp", "time", "ts", "@timestamp", "datetime", "date")
_LEVEL_KEYS = ("level", "severity", "lvl", "loglevel", "priority")
_MESSAGE_KEYS = ("message", "msg", "log", "event", "description")

_COMMON_ALIASES: dict[str, str] = {
    "ts": "timestamp",
    "@timestamp": "timestamp",
    "time": "timestamp",
    "datetime": "timestamp",
    "date": "timestamp",
    "lvl": "level",
    "loglevel": "level",
    "severity": "level",
    "priority": "level",
    "msg": "message",
    "log": "message",
    "event": "message",
    "description": "message",
}


def parse_json_line(
    line: str,
    source: str | None = None,
    line_no: int | None = None,
) -> Record | None:
    """Parse one JSON-lines entry; ``None`` means "not JSON, try another parser".

    Nested objects are flattened one level (``http.status`` → ``http_status``)
    so filters can address them without dotted paths.
    """
    stripped = line.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload: dict[str, Any] = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return _to_record(payload, line, source, line_no)


def _to_record(
    payload: dict[str, Any],
    raw: str,
    source: str | None,
    line_no: int | None,
) -> Record:
    fields = _flatten(payload)
    return Record(
        raw=raw,
        message=_pick(fields, _MESSAGE_KEYS),
        timestamp=_timestamp_from(fields),
        level=_level_from(fields),
        fields=fields,
        source=source,
        line_no=line_no,
    )


def _flatten(payload: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in payload.items():
        key = key.lstrip("@")
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}_{sub_key}".lstrip("@")] = sub_value
        else:
            flat[key] = value
    return flat


def _pick(fields: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        for candidate in (key, _COMMON_ALIASES.get(key, key)):
            if candidate in fields and fields[candidate] not in (None, ""):
                return fields[candidate]
    return ""


def _timestamp_from(fields: dict[str, Any]):
    from loglens.timestamps import TimestampParser

    raw = _pick(fields, _TIMESTAMP_KEYS)
    if isinstance(raw, str):
        return TimestampParser().parse(raw)
    return None


def _level_from(fields: dict[str, Any]) -> str | None:
    from loglens.levels import normalize_level

    return normalize_level(_pick(fields, _LEVEL_KEYS))


def looks_like_json(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("{"):
        return False
    try:
        value = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(value, dict)


def render_value(value: Any) -> str:
    """Render a field value for filters and reports."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
    return str(value)
