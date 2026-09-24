"""M42f — interval windows over timestamps for range queries."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime

from loglens.timestamps import to_utc


@dataclass
class Window:
    """A half-open [start, end) interval with a label."""

    start: datetime
    end: datetime
    label: str = ""

    def contains(self, moment: datetime) -> bool:
        moment = to_utc(moment)
        return to_utc(self.start) <= moment < to_utc(self.end)

    def duration_seconds(self) -> float:
        return (to_utc(self.end) - to_utc(self.start)).total_seconds()


class WindowIndex:
    """Sorted windows supporting 'which windows cover this moment' queries."""

    def __init__(self, windows: list[Window]):
        self.windows = sorted(windows, key=lambda w: to_utc(w.start))
        self._starts = [to_utc(w.start).timestamp() for w in self.windows]

    def covering(self, moment: datetime) -> list[Window]:
        """All windows whose start <= moment < end."""
        ts = to_utc(moment).timestamp()
        # candidate windows start at or before the moment
        upper = bisect_right(self._starts, ts)
        out = []
        for window in self.windows[:upper]:
            if to_utc(window.end).timestamp() > ts:
                out.append(window)
        return out

    def first_covering(self, moment: datetime) -> Window | None:
        hits = self.covering(moment)
        return hits[0] if hits else None

    def total_coverage_seconds(self) -> float:
        """Sum of non-overlapping covered time (merged intervals)."""
        if not self.windows:
            return 0.0
        merged: list[list[float]] = []
        for window in self.windows:
            start = to_utc(window.start).timestamp()
            end = to_utc(window.end).timestamp()
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        return sum(end - start for start, end in merged)


def tag_records_with_windows(records, index: WindowIndex) -> dict[str, int]:
    """Count records per window label (records may hit several windows)."""
    counts: dict[str, int] = {}
    for rec in records:
        if rec.timestamp is None:
            continue
        for window in index.covering(rec.timestamp):
            counts[window.label] = counts.get(window.label, 0) + 1
    return counts


def gaps_between(windows: list[Window]) -> list[tuple[datetime, datetime]]:
    """Uncovered spans between consecutive sorted windows."""
    ordered = sorted(windows, key=lambda w: to_utc(w.start))
    gaps = []
    for i in range(1, len(ordered)):
        prev_end = to_utc(ordered[i - 1].end)
        start = to_utc(ordered[i].start)
        if start > prev_end:
            gaps.append((prev_end, start))
    return gaps
