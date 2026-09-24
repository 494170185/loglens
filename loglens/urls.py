"""M25 — URL breakdown: path, query params, segments."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit


def break_down_url(url: str) -> dict[str, object]:
    """Split a URL into scheme/host/path/query fields (log-safe).

    Query parameters become individual ``q_<name>`` fields holding the
    last value; the full mapping is kept under ``query_params``.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return {"url": url}
    fields: dict[str, object] = {"url": url}
    if parts.scheme:
        fields["scheme"] = parts.scheme
    if parts.netloc:
        fields["host"] = parts.netloc
    fields["path"] = parts.path or "/"
    if parts.query:
        params = parse_qs(parts.query, keep_blank_values=True)
        fields["query_params"] = {k: v[-1] for k, v in params.items()}
        for key, values in params.items():
            fields[f"q_{key}"] = values[-1]
    if parts.fragment:
        fields["fragment"] = parts.fragment
    return fields


def path_segments(path: str) -> list[str]:
    """Non-empty path segments: ``/a/b/c`` -> ['a', 'b', 'c']."""
    return [seg for seg in path.split("/") if seg]


def route_shape(path: str) -> str:
    """Collapse a path to its route shape by replacing numeric segments.

    ``/api/users/42/orders/7`` -> ``/api/users/:id/orders/:id``; long hex
    or uuid-like segments become ``:hash``.
    """
    segments = path_segments(path)
    out = []
    for seg in segments:
        if seg.isdigit():
            out.append(":id")
        elif len(seg) >= 12 and all(c in "0123456789abcdefABCDEF" for c in seg):
            out.append(":hash")
        else:
            out.append(seg)
    return "/" + "/".join(out)


def normalize_path(path: str) -> str:
    """Route shape with query-independent, trailing-slash-removed form."""
    trimmed = path.split("?")[0]
    if len(trimmed) > 1 and trimmed.endswith("/"):
        trimmed = trimmed[:-1]
    return route_shape(trimmed)


def enrich_record_with_url(fields: dict[str, object], url_key: str = "path") -> dict[str, object]:
    """Merge URL breakdown fields into a record's field mapping."""
    raw = fields.get(url_key) or fields.get("url")
    if not isinstance(raw, str) or not raw:
        return fields
    merged = dict(fields)
    merged.update(break_down_url(raw))
    return merged
