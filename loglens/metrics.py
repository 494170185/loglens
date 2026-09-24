"""M17 — numeric metrics over record fields."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from loglens.model import Record


def numeric_series(records: Iterable[Record], field: str) -> list[float]:
    """Collect parseable numeric values of *field* across records."""
    from loglens.aggregate import field_value

    out: list[float] = []
    for rec in records:
        value = field_value(rec, field)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out.append(float(value))
        elif isinstance(value, str):
            try:
                out.append(float(value))
            except ValueError:
                continue
    return out


@dataclass
class Summary:
    count: int
    total: float
    mean: float
    min: float
    max: float
    median: float
    p95: float
    p99: float
    stdev: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "total": self.total,
            "mean": self.mean,
            "min": self.min,
            "max": self.max,
            "median": self.median,
            "p95": self.p95,
            "p99": self.p99,
            "stdev": self.stdev,
        }


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile; 95 means the 95th percentile."""
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = math.ceil(pct / 100 * len(ordered))
    rank = max(1, min(rank, len(ordered)))
    return ordered[rank - 1]


def summarize(values: list[float]) -> Summary:
    """Full descriptive summary of a numeric series."""
    if not values:
        raise ValueError("summarize of empty list")
    total = sum(values)
    mean = total / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return Summary(
        count=len(values),
        total=total,
        mean=mean,
        min=min(values),
        max=max(values),
        median=percentile(values, 50),
        p95=percentile(values, 95),
        p99=percentile(values, 99),
        stdev=math.sqrt(variance),
    )


def summarize_field(records: Iterable[Record], field: str) -> Summary | None:
    values = numeric_series(records, field)
    if not values:
        return None
    return summarize(values)


@dataclass
class StatusBreakdown:
    """Counts grouped by HTTP status class and exact code."""

    counts: Counter
    class_counts: Counter

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def error_rate(self) -> float:
        """Fraction of responses that were 5xx."""
        total = self.total
        if total == 0:
            return 0.0
        return self.class_counts.get("5xx", 0) / total


def status_breakdown(records: Iterable[Record]) -> StatusBreakdown:
    """Tally status codes and their 2xx..5xx classes."""
    from loglens.aggregate import field_value
    from loglens.parsers.access import status_class

    counts: Counter = Counter()
    class_counts: Counter = Counter()
    for rec in records:
        status = field_value(rec, "status")
        if isinstance(status, bool) or status is None:
            continue
        try:
            code = int(status)
        except (TypeError, ValueError):
            continue
        counts[code] += 1
        class_counts[status_class(code)] += 1
    return StatusBreakdown(counts=counts, class_counts=class_counts)


def rate_per_second(count: int, seconds: float) -> float:
    """Events per second over a window; guards divide-by-zero."""
    if seconds <= 0:
        return 0.0
    return count / seconds
