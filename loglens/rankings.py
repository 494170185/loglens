"""M18/M19 — top-N rankings and ASCII histograms."""

from __future__ import annotations

from collections.abc import Iterable

from loglens.aggregate import Group, group_by
from loglens.metrics import numeric_series, percentile, summarize
from loglens.model import Record

DEFAULT_BAR_WIDTH = 40
DEFAULT_HIST_BINS = 20


def top_groups(
    records: Iterable[Record],
    field: str,
    n: int = 10,
    by: str = "count",
) -> list[Group]:
    """The *n* groups (by *field*) with the highest count or metric."""
    groups = group_by(records, field)
    if by == "count":
        groups.sort(key=lambda g: g.count, reverse=True)
    elif by.startswith("avg:"):
        groups.sort(key=lambda g: _avg(g, by[4:]), reverse=True)
    elif by.startswith("sum:"):
        groups.sort(key=lambda g: sum(g.numeric_values(by[4:])), reverse=True)
    elif by.startswith("max:"):
        groups.sort(
            key=lambda g: (max(g.numeric_values(by[4:]), default=0.0)), reverse=True
        )
    else:
        raise ValueError(f"unknown ranking {by!r}")
    return groups[:n]


def _avg(group: Group, field: str) -> float:
    values = group.numeric_values(field)
    return sum(values) / len(values) if values else 0.0


def render_bar(value: float, max_value: float, width: int = DEFAULT_BAR_WIDTH) -> str:
    """A bar of '#' characters proportional to value/max."""
    if max_value <= 0:
        return ""
    ratio = min(value / max_value, 1.0)
    return "#" * round(ratio * width)


def histogram_ascii(
    values: list[float],
    bins: int = DEFAULT_HIST_BINS,
    width: int = DEFAULT_BAR_WIDTH,
) -> list[str]:
    """Render a value distribution as ``(label, bar)`` text lines."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [f"{_format_edge(lo)} | {'#' * width} {len(values)}"]
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = int((v - lo) / step)
        idx = min(idx, bins - 1)
        counts[idx] += 1
    peak = max(counts)
    lines = []
    for i, count in enumerate(counts):
        if count == 0:
            continue
        label = _format_edge(lo + i * step)
        lines.append(f"{label} | {render_bar(count, peak, width)} {count}")
    return lines


def _format_edge(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def field_histogram(
    records: Iterable[Record],
    field: str,
    bins: int = DEFAULT_HIST_BINS,
    width: int = DEFAULT_BAR_WIDTH,
) -> list[str]:
    """Histogram of a numeric field across records."""
    return histogram_ascii(numeric_series(records, field), bins=bins, width=width)


def outliers(
    records: Iterable[Record],
    field: str,
    threshold_pct: float = 99.0,
) -> list[Record]:
    """Records whose *field* value sits above the given percentile."""
    values = numeric_series(records, field)
    if not values:
        return []
    cutoff = percentile(values, threshold_pct)
    from loglens.aggregate import field_value

    out = []
    for rec in records:
        value = field_value(rec, field)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and (
            float(value) > cutoff
        ):
            out.append(rec)
    return out


def latency_profile(records: Iterable[Record], field: str = "dur") -> dict[str, float]:
    """Common latency SLO profile: mean, p50, p95, p99, max."""
    values = numeric_series(records, field)
    if not values:
        return {}
    s = summarize(values)
    return {
        "mean": round(s.mean, 3),
        "p50": s.median,
        "p95": s.p95,
        "p99": s.p99,
        "max": s.max,
    }
