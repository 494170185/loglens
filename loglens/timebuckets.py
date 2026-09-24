"""M20 — time bucketing: series over fixed windows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loglens.model import Record
from loglens.timestamps import round_to_bucket, to_utc

BUCKET_SIZES = {
    "10s": 10,
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}


@dataclass
class TimeBucket:
    start: datetime
    records: list[Record]

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(seconds=self.size)

    size: int = 0


def bucket_records(
    records: Iterable[Record],
    size: str | int = "1m",
) -> list[TimeBucket]:
    """Group timestamped records into fixed windows of *size*.

    ``size`` is either a ``BUCKET_SIZES`` key ('5m') or a second count.
    Records without timestamps are skipped. Buckets with zero records
    between the first and last bucket are filled in as empty buckets.
    """
    seconds = BUCKET_SIZES[size] if isinstance(size, str) else int(size)
    buckets: dict[datetime, list[Record]] = {}
    for rec in records:
        if rec.timestamp is None:
            continue
        start = round_to_bucket(rec.timestamp, seconds)
        buckets.setdefault(start, []).append(rec)
    if not buckets:
        return []
    starts = sorted(buckets)
    out: list[TimeBucket] = []
    cursor = starts[0]
    last = starts[-1]
    while cursor <= last:
        out.append(
            TimeBucket(start=cursor, records=buckets.get(cursor, []), size=seconds)
        )
        cursor += timedelta(seconds=seconds)
    return out


def bucket_counts(records: Iterable[Record], size: str | int = "1m") -> list[tuple[datetime, int]]:
    """(bucket_start, count) pairs, gaps filled with zero."""
    return [(b.start, b.count) for b in bucket_records(records, size)]


def rate_series(
    records: Iterable[Record],
    size: str | int = "1m",
) -> list[tuple[datetime, float]]:
    """Events per second per bucket."""
    seconds = BUCKET_SIZES[size] if isinstance(size, str) else int(size)
    return [(start, count / seconds) for start, count in bucket_counts(records, size)]


def error_rate_series(
    records: Iterable[Record],
    size: str | int = "1m",
) -> list[tuple[datetime, float]]:
    """Fraction of 5xx per bucket (records with no status excluded)."""
    out = []
    for bucket in bucket_records(records, size):
        total = 0
        errors = 0
        for rec in bucket.records:
            status = rec.get("status")
            if status is None:
                continue
            try:
                code = int(status)
            except (TypeError, ValueError):
                continue
            total += 1
            if code >= 500:
                errors += 1
        rate = errors / total if total else 0.0
        out.append((bucket.start, rate))
    return out


def window_slice(
    records: Iterable[Record],
    start: datetime,
    end: datetime,
) -> list[Record]:
    """Records with timestamps inside [start, end]."""
    start = to_utc(start)
    end = to_utc(end)
    return [
        rec
        for rec in records
        if rec.timestamp is not None and start <= to_utc(rec.timestamp) <= end
    ]


def time_span(records: Iterable[Record]) -> tuple[datetime, datetime] | None:
    """First and last timestamps in the stream, or None if none have one."""
    stamps = [to_utc(rec.timestamp) for rec in records if rec.timestamp is not None]
    if not stamps:
        return None
    return min(stamps), max(stamps)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)
