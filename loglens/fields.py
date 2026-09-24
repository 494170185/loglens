"""M42e — field inventory: which fields exist and how often they're set."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from loglens.model import Record


@dataclass
class FieldStats:
    name: str
    present: int
    total: int

    @property
    def coverage(self) -> float:
        return self.present / self.total if self.total else 0.0

    @property
    def is_sparse(self) -> bool:
        return 0 < self.coverage < 0.1


def field_inventory(records: Iterable[Record], include_builtins: bool = False) -> list[FieldStats]:
    """Which record keys appear, and how often, sorted by coverage."""
    records = list(records)
    total = len(records)
    counts: Counter = Counter()
    for rec in records:
        keys = set(rec.fields)
        if include_builtins:
            if rec.level:
                keys.add("level")
            if rec.timestamp:
                keys.add("timestamp")
        counts.update(keys)
    stats = [FieldStats(name=name, present=cnt, total=total) for name, cnt in counts.items()]
    return sorted(stats, key=lambda s: s.coverage, reverse=True)


def value_histogram(records: Iterable[Record], field: str, top: int = 10) -> list[tuple[str, int]]:
    """Most common values of one field."""
    counts: Counter = Counter()
    for rec in records:
        value = rec.get(field)
        if value is None:
            continue
        counts[str(value)] += 1
    return counts.most_common(top)


def numeric_fields(records: Iterable[Record]) -> list[str]:
    """Field names that look numeric across the stream."""
    from loglens.aggregate import field_value

    numeric: set[str] = set()
    seen: set[str] = set()
    for rec in records:
        for key in rec.fields:
            if key in seen:
                continue
            value = field_value(rec, key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric.add(key)
                seen.add(key)
    return sorted(numeric)
