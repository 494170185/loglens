"""M29/M30 — anomaly detection and silence gaps."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from loglens.model import Record
from loglens.timestamps import to_utc


@dataclass
class Anomaly:
    """One record whose numeric field deviates strongly from the mean."""

    field: str
    value: float
    mean: float
    stdev: float
    zscore: float
    record: Record


def detect_anomalies(
    records: Iterable[Record],
    field: str,
    min_z: float = 3.0,
) -> list[Anomaly]:
    """Records whose *field* value is at least *min_z* standard deviations out.

    Population stdev is used; a series with zero stdev produces no
    anomalies (a constant stream is not anomalous by this measure).
    """
    from loglens.aggregate import field_value

    materialized = list(records)
    values: list[float] = []
    for rec in materialized:
        value = field_value(rec, field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    if len(values) < 3:
        return []
    mean = sum(values) / len(values)
    stdev = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    if stdev == 0:
        return []
    out: list[Anomaly] = []
    for rec in materialized:
        value = field_value(rec, field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            z = (float(value) - mean) / stdev
            if abs(z) >= min_z:
                out.append(
                    Anomaly(
                        field=field,
                        value=float(value),
                        mean=mean,
                        stdev=stdev,
                        zscore=round(z, 2),
                        record=rec,
                    )
                )
    return out


@dataclass
class Silence:
    """A period with no timestamped records between two events."""

    start: datetime  # last record before the gap
    end: datetime  # first record after the gap
    seconds: float

    @property
    def minutes(self) -> float:
        return self.seconds / 60


def detect_silences(
    records: Iterable[Record],
    min_seconds: float = 300.0,
) -> list[Silence]:
    """Timestamp gaps of at least *min_seconds* between consecutive records."""
    stamps = sorted(to_utc(rec.timestamp) for rec in records if rec.timestamp is not None)
    out: list[Silence] = []
    for i in range(1, len(stamps)):
        delta = (stamps[i] - stamps[i - 1]).total_seconds()
        if delta >= min_seconds:
            out.append(
                Silence(start=stamps[i - 1], end=stamps[i], seconds=delta)
            )
    return out


@dataclass
class FreshnessReport:
    """How long since the last record; for 'is the log still live?' checks."""

    last_seen: datetime | None
    age_seconds: float | None

    @property
    def is_stale(self) -> bool:
        return self.age_seconds is None or self.age_seconds > 3600


def freshness(records: Iterable[Record], now: datetime) -> FreshnessReport:
    """Age of the newest record relative to *now*."""
    stamps = [to_utc(rec.timestamp) for rec in records if rec.timestamp is not None]
    if not stamps:
        return FreshnessReport(last_seen=None, age_seconds=None)
    last = max(stamps)
    return FreshnessReport(last_seen=last, age_seconds=(now - last).total_seconds())


def long_running(
    records: Iterable[Record],
    field: str = "dur",
    threshold: float = 1000.0,
) -> list[Record]:
    """Records whose *field* value exceeds a fixed threshold."""
    from loglens.aggregate import field_value

    out = []
    for rec in records:
        value = field_value(rec, field)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and float(value) > threshold
        ):
            out.append(rec)
    return out


def gap_windows(
    silences: list[Silence],
    width: timedelta | None = None,
) -> list[tuple[datetime, datetime]]:
    """(start, end) tuples, optionally widened for display context."""
    if width is None:
        return [(s.start, s.end) for s in silences]
    return [(s.start - width, s.end + width) for s in silences]
