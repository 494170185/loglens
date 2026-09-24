"""M11 — extract structured fields from free-text messages."""

from __future__ import annotations

import re

from loglens.model import Record

IPV4_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
DURATION_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s\b|sec(?:onds?)?|m\b|min(?:utes?)?|"
    r"h\b|hr|hours?|us|µs|microseconds?|ns|nanoseconds?)\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"\bhttps?://[^\s\"'<>\]]+")
PATH_RE = re.compile(r"(?<![\w])/(?:[\w.-]+/)*[\w.-]+")
HEX_RE = re.compile(r"\b[0-9a-fA-F]{8,}\b")
KV_RE = re.compile(
    r"\b([a-z_][a-z0-9_]{1,20})(?:=|:\s)(\"[^\"]{0,40}\"|\S{1,40})"
)

_UNIT_TO_MS = {
    "ns": 0.000001,
    "nanoseconds": 0.000001,
    "nanosecond": 0.000001,
    "us": 0.001,
    "µs": 0.001,
    "microseconds": 0.001,
    "microsecond": 0.001,
    "ms": 1.0,
    "milliseconds": 1.0,
    "millisecond": 1.0,
    "s": 1000.0,
    "sec": 1000.0,
    "secs": 1000.0,
    "second": 1000.0,
    "seconds": 1000.0,
    "m": 60_000.0,
    "min": 60_000.0,
    "mins": 60_000.0,
    "minute": 60_000.0,
    "minutes": 60_000.0,
    "h": 3_600_000.0,
    "hr": 3_600_000.0,
    "hrs": 3_600_000.0,
    "hour": 3_600_000.0,
    "hours": 3_600_000.0,
}


def is_ipv4(text: str) -> bool:
    m = IPV4_RE.fullmatch(text)
    if not m:
        return False
    return all(0 <= int(part) <= 255 for part in text.split("."))


def extract_ips(text: str) -> list[str]:
    return [m.group(1) for m in IPV4_RE.finditer(text) if is_ipv4(m.group(1))]


def extract_uuids(text: str) -> list[str]:
    return UUID_RE.findall(text)


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text)


def extract_durations_ms(text: str) -> list[float]:
    """All durations in *text*, normalized to milliseconds."""
    out = []
    for m in DURATION_RE.finditer(text):
        value = float(m.group(1))
        unit = m.group(2).lower().rstrip(".")
        factor = _UNIT_TO_MS.get(unit)
        if factor is None:
            continue
        out.append(round(value * factor, 6))
    return out


def extract_kvs(text: str) -> dict[str, str]:
    """Loose ``key=value`` / ``key: value`` pairs inside free text."""
    out: dict[str, str] = {}
    for m in KV_RE.finditer(text):
        key, value = m.group(1), m.group(2)
        out[key] = value.strip("\"'")
    return out


def extract_paths(text: str) -> list[str]:
    """Absolute Unix-style paths (must start with / and have a name)."""
    return [m.group(0) for m in PATH_RE.finditer(text) if len(m.group(0)) > 1]


_EXTRACTORS = {
    "ip": extract_ips,
    "uuid": extract_uuids,
    "url": extract_urls,
    "duration_ms": extract_durations_ms,
    "path": extract_paths,
}


def enrich(record: Record, kinds: tuple[str, ...] | None = None) -> Record:
    """Return a copy of *record* with extracted fields merged in.

    Extracted values land under ``ip``/``ips``-style keys: the first value
    under the singular key, and the full list under the plural key when
    there is more than one.
    """
    kinds = kinds or ("ip", "uuid", "url", "duration_ms", "path")
    text = record.message or record.raw
    extra: dict[str, object] = {}
    for kind in kinds:
        if kind not in _EXTRACTORS:
            continue
        values = _EXTRACTORS[kind](text)
        if not values:
            continue
        plural = f"{kind}s"
        extra[plural] = values
        extra[kind] = values[0]
    extra.update(extract_kvs(text))
    return record.merged(extra)
