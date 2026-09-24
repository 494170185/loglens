"""M42h — threshold tuning helpers for the detectors.

Picks sane detector parameters from historical data instead of magic
numbers: how many repeats count as a burst, what gap counts as silence,
and what z-score to use for anomaly flagging.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from loglens.bursts import normalize_message
from loglens.model import Record
from loglens.timestamps import to_utc


def suggest_burst_threshold(records: Iterable[Record], sensitivity: float = 3.0) -> int:
    """A repeat-count threshold tuned to the stream's message diversity.

    With few distinct messages, small runs are normal and the bar rises;
    with high diversity, even short runs are meaningful. The result is
    always at least 3.
    """
    materialized = list(records)
    if not materialized:
        return 5
    distinct = len({normalize_message(r.message or r.raw.split("\n")[0]) for r in materialized})
    total = len(materialized)
    if distinct == 0:
        return 5
    # expected repeats per message if uniformly spread
    spread = total / distinct
    threshold = max(3, round(spread * sensitivity))
    return min(threshold, max(3, total // 2))


def suggest_silence_threshold(records: Iterable[Record], factor: float = 10.0) -> float:
    """A gap threshold at *factor* times the median inter-arrival time."""
    stamps = sorted(to_utc(r.timestamp) for r in records if r.timestamp is not None)
    if len(stamps) < 3:
        return 300.0
    gaps = [
        (stamps[i] - stamps[i - 1]).total_seconds() for i in range(1, len(stamps))
    ]
    gaps.sort()
    median = gaps[len(gaps) // 2]
    if median <= 0:
        return 300.0
    return max(60.0, round(median * factor, 1))


def suggest_z_threshold(records: Iterable[Record], field: str, false_positive_rate: float = 0.01) -> float:
    """A z-score cutoff for the anomaly detector given a target FP rate.

    Uses the normal approximation: the quantile z such that P(|Z| > z)
    equals *false_positive_rate*.
    """
    from loglens.metrics import numeric_series

    values = numeric_series(records, field)
    if len(values) < 30:
        return 3.0
    # inverse normal quantile for common rates (no scipy allowed)
    table = {0.10: 1.645, 0.05: 1.96, 0.02: 2.326, 0.01: 2.576, 0.005: 2.807, 0.001: 3.291}
    closest = min(table, key=lambda k: abs(k - false_positive_rate))
    return table[closest]


def level_mix(records: Iterable[Record]) -> dict[str, float]:
    """Fraction of records per severity (missing levels excluded)."""
    counts: Counter = Counter(r.level for r in records if r.level)
    total = sum(counts.values())
    if total == 0:
        return {}
    return {level: count / total for level, count in counts.items()}


def noisiest_hours(records: Iterable[Record], top: int = 3) -> list[tuple[int, int]]:
    """UTC hours with the most events: (hour, count)."""
    counts: Counter = Counter()
    for rec in records:
        if rec.timestamp is not None:
            counts[to_utc(rec.timestamp).hour] += 1
    return counts.most_common(top)
