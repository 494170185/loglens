"""M42b — correlate events across two record streams by timestamp."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from loglens.model import Record
from loglens.timestamps import to_utc


@dataclass
class Correlation:
    """A pair of records from two streams within the tolerance window."""

    left: Record
    right: Record
    delta_seconds: float  # right.timestamp - left.timestamp


def correlate_streams(
    left: Iterable[Record],
    right: Iterable[Record],
    within_seconds: float = 1.0,
) -> list[Correlation]:
    """Match records from two streams by closest timestamp.

    Both streams are sorted by timestamp first. Each right-hand record
    matches at most the single closest left-hand record inside the window
    (greedy, in time order).
    """
    left_stamped = sorted(
        [r for r in left if r.timestamp is not None],
        key=lambda r: to_utc(r.timestamp),
    )
    right_stamped = sorted(
        [r for r in right if r.timestamp is not None],
        key=lambda r: to_utc(r.timestamp),
    )
    out: list[Correlation] = []
    i = 0
    for r in right_stamped:
        rt = to_utc(r.timestamp)
        # advance left pointer past records that can never match again
        while i < len(left_stamped):
            lt = to_utc(left_stamped[i].timestamp)
            if (rt - lt).total_seconds() > within_seconds:
                i += 1
            else:
                break
        if i >= len(left_stamped):
            break
        best = left_stamped[i]
        delta = (rt - to_utc(best.timestamp)).total_seconds()
        if abs(delta) <= within_seconds:
            out.append(Correlation(left=best, right=r, delta_seconds=round(delta, 6)))
    return out


def join_by_field(
    left: Iterable[Record],
    right: Iterable[Record],
    field: str,
) -> list[tuple[Record, Record]]:
    """Inner join of two streams on an exact field value."""
    from loglens.aggregate import field_value

    index: dict[str, list[Record]] = {}
    for rec in left:
        key = field_value(rec, field)
        if key is not None:
            index.setdefault(str(key), []).append(rec)
    pairs: list[tuple[Record, Record]] = []
    for rec in right:
        key = field_value(rec, field)
        if key is not None:
            for match in index.get(str(key), []):
                pairs.append((match, rec))
    return pairs


def co_occurrence(
    records: Iterable[Record],
    field_a: str,
    field_b: str,
) -> dict[tuple[str, str], int]:
    """Count how often two field values appear on the same record."""
    from loglens.aggregate import field_value

    counts: dict[tuple[str, str], int] = {}
    for rec in records:
        a = field_value(rec, field_a)
        b = field_value(rec, field_b)
        if a is None or b is None:
            continue
        key = (str(a), str(b))
        counts[key] = counts.get(key, 0) + 1
    return counts
