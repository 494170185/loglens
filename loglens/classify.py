"""M21 — request classification by path, method and content type."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from loglens.model import Record

# Path taxonomy used by the classify command. Patterns are checked in
# order; the first match wins.
_PATH_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api", re.compile(r"^/api/|^/v\d+/")),
    ("static", re.compile(
        r"\.(css|js|png|jpe?g|gif|svg|ico|woff2?|ttf|map|txt|xml)(\?|$)", re.I
    )),
    ("auth", re.compile(r"/(login|logout|signin|signup|oauth|token|auth)")),
    ("health", re.compile(r"/(health|healthz|ready|readiness|livez|ping|status)$")),
    ("admin", re.compile(r"^/(admin|manage|internal)/")),
    ("assets", re.compile(r"^/(assets|static|public|dist)/")),
    ("webhook", re.compile(r"/(webhook|callback|hooks?)/")),
)

_METHOD_WEIGHTS = {"GET": "read", "HEAD": "read", "POST": "write", "PUT": "write",
                   "PATCH": "write", "DELETE": "write", "OPTIONS": "meta"}


def classify_path(path: str | None) -> str:
    """Bucket a URL path into the taxonomy above; 'other' by default."""
    if not path:
        return "other"
    for label, pattern in _PATH_RULES:
        if pattern.search(path):
            return label
    return "other"


def classify_method(method: str | None) -> str:
    """Group an HTTP verb into read/write/meta."""
    if not method:
        return "unknown"
    return _METHOD_WEIGHTS.get(method.upper(), "unknown")


def mime_of(path: str | None) -> str:
    """Best-effort MIME type from a path extension."""
    if not path:
        return "unknown"
    ext = path.split("?")[0].rsplit(".", 1)[-1].lower() if "." in path else ""
    return _EXT_TO_MIME.get(ext, "unknown")


_EXT_TO_MIME = {
    "html": "text/html", "htm": "text/html", "css": "text/css",
    "js": "application/javascript", "mjs": "application/javascript",
    "json": "application/json", "xml": "application/xml",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "svg": "image/svg+xml", "ico": "image/x-icon",
    "webp": "image/webp", "woff": "font/woff", "woff2": "font/woff2",
    "ttf": "font/ttf", "txt": "text/plain", "csv": "text/csv",
    "pdf": "application/pdf", "zip": "application/zip",
    "gz": "application/gzip", "mp4": "video/mp4", "webm": "video/webm",
}


def classify_request(record: Record) -> dict[str, str]:
    """Classification bundle for one access-log record."""
    path = record.get("path")
    method = record.get("method")
    return {
        "category": classify_path(path if isinstance(path, str) else None),
        "verb_group": classify_method(method if isinstance(method, str) else None),
        "mime": mime_of(path if isinstance(path, str) else None),
    }


def category_counts(records: Iterable[Record]) -> Counter:
    """Tally requests by path category."""
    return Counter(classify_request(rec)["category"] for rec in records)


def slowest_categories(
    records: Iterable[Record],
    field: str = "dur",
    top: int = 5,
) -> list[tuple[str, float]]:
    """Categories ranked by mean value of *field* (e.g. latency)."""
    from loglens.aggregate import field_value

    buckets: dict[str, list[float]] = {}
    for rec in records:
        category = classify_request(rec)["category"]
        value = field_value(rec, field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            buckets.setdefault(category, []).append(float(value))
    ranked = sorted(
        ((name, sum(vals) / len(vals)) for name, vals in buckets.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    return ranked[:top]
