"""M22 — rate-shift detection: find where traffic suddenly changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loglens.model import Record
from loglens.timebuckets import bucket_counts, rate_series


@dataclass
class Shift:
    """A detected change in event rate between adjacent buckets."""

    at: datetime
    before: float  # events/sec before the shift
    after: float  # events/sec after the shift
    ratio: float  # after / before

    @property
    def direction(self) -> str:
        if self.after > self.before:
            return "spike"
        return "drop"


def detect_shifts(
    records: list[Record],
    size: str | int = "1m",
    min_ratio: float = 3.0,
    min_count: int = 3,
) -> list[Shift]:
    """Adjacent-bucket rate changes where ``after/before >= min_ratio``.

    Buckets with fewer than *min_count* events on the small side are
    ignored, so quiet files do not produce noise shifts.
    """
    series = rate_series(records, size)
    counts = dict(bucket_counts(records, size))
    shifts: list[Shift] = []
    for i in range(1, len(series)):
        prev_at, prev_rate = series[i - 1]
        at, rate = series[i]
        prev_count = counts.get(prev_at, 0)
        if prev_count < min_count:
            continue
        ratio = rate / prev_rate if prev_rate > 0 else 0.0
        # epsilon guard: 9/3 events can divide to 2.9999... in floats
        up = ratio >= min_ratio * (1 - 1e-9)
        down = prev_rate > 0 and ratio <= (1 / min_ratio) * (1 + 1e-9)
        if up or down:
            shifts.append(
                Shift(at=at, before=prev_rate, after=rate, ratio=round(ratio, 3))
            )
    return shifts


@dataclass
class Spike:
    """A single bucket whose count stands far above its neighbors."""

    at: datetime
    count: int
    baseline: float  # mean of the neighboring buckets
    factor: float  # count / baseline


def detect_spikes(
    records: list[Record],
    size: str | int = "1m",
    factor: float = 5.0,
) -> list[Spike]:
    """Buckets at least *factor* times the mean of their neighbors."""
    counts = bucket_counts(records, size)
    if len(counts) < 3:
        return []
    out: list[Spike] = []
    for i in range(1, len(counts) - 1):
        at, count = counts[i]
        neighbors = [counts[i - 1][1], counts[i + 1][1]]
        baseline = sum(neighbors) / len(neighbors)
        if baseline <= 0:
            continue
        if count / baseline >= factor:
            out.append(
                Spike(at=at, count=count, baseline=baseline, factor=round(count / baseline, 2))
            )
    return out


def summarize_shifts(shifts: list[Shift]) -> str:
    """One-line human summary for reports."""
    if not shifts:
        return "no rate shifts detected"
    parts = []
    for s in shifts:
        arrow = "up" if s.direction == "spike" else "down"
        parts.append(f"{s.at.strftime('%H:%M')} {arrow} x{s.ratio:.1f}")
    return "; ".join(parts)
