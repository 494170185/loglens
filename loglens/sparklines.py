"""M42e — sparklines: compact time-series glyphs for terminals."""

from __future__ import annotations

from collections.abc import Iterable

BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 40) -> str:
    """Render a numeric series as unicode block characters.

    Empty input renders as an empty string; a flat series renders as the
    lowest block repeated.
    """
    if not values:
        return ""
    if width <= 0:
        raise ValueError("width must be positive")
    series = _normalize_count(values, width)
    lo, hi = min(series), max(series)
    span = hi - lo
    out = []
    for v in series:
        if span == 0:
            out.append(BLOCKS[0])
        else:
            idx = int((v - lo) / span * (len(BLOCKS) - 1))
            out.append(BLOCKS[idx])
    return "".join(out)


def _normalize_count(values: list[float], width: int) -> list[float]:
    """Downsample (or keep) the series to exactly *width* points."""
    if len(values) == width:
        return values
    if len(values) < width:
        # upsample by repeating proportionally
        out = []
        for i in range(width):
            pos = i * len(values) / width
            out.append(values[min(int(pos), len(values) - 1)])
        return out
    # downsample by averaging buckets
    out = []
    bucket = len(values) / width
    for i in range(width):
        start = int(i * bucket)
        end = max(start + 1, int((i + 1) * bucket))
        chunk = values[start:end]
        out.append(sum(chunk) / len(chunk))
    return out


def trend_arrow(values: list[float]) -> str:
    """One-character trend: rising, falling, or flat."""
    if len(values) < 2:
        return "→"
    first, last = values[0], values[-1]
    if last > first * 1.05:
        return "↗"
    if last < first * 0.95:
        return "↘"
    return "→"


def series_summary(values: list[float]) -> str:
    """Compact 'min/mean/max' rendering next to a sparkline."""
    if not values:
        return "-"
    mean = sum(values) / len(values)
    return f"{min(values):.0f}/{mean:.0f}/{max(values):.0f}"


def render_counts_series(pairs: Iterable[tuple[object, int]]) -> str:
    """Sparkline for (bucket, count) time-bucket pairs."""
    counts = [count for _bucket, count in pairs]
    return sparkline(counts)
