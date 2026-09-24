"""M42c — diff two record sets for log comparison (before/after restarts)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from loglens.bursts import normalize_message
from loglens.model import Record


@dataclass
class DiffReport:
    """What changed between two collections."""

    only_before: list[str]  # normalized messages present before, not after
    only_after: list[str]
    count_changes: list[tuple[str, int, int]]  # (message, before, after)

    @property
    def has_changes(self) -> bool:
        return bool(self.only_before or self.only_after or self.count_changes)


def message_counts(records: Iterable[Record]) -> Counter:
    return Counter(normalize_message(r.message or r.raw.split("\n")[0]) for r in records)


def diff_records(before: Iterable[Record], after: Iterable[Record]) -> DiffReport:
    """Compare normalized message frequencies between two streams."""
    counts_before = message_counts(before)
    counts_after = message_counts(after)
    only_before = sorted(set(counts_before) - set(counts_after))
    only_after = sorted(set(counts_after) - set(counts_before))
    changes = []
    for msg in sorted(set(counts_before) & set(counts_after)):
        b, a = counts_before[msg], counts_after[msg]
        if b != a:
            changes.append((msg, b, a))
    return DiffReport(
        only_before=only_before, only_after=only_after, count_changes=changes
    )


def field_diff(
    before: Iterable[Record],
    after: Iterable[Record],
    field: str,
) -> dict[str, tuple[object, object]]:
    """First-value diff of a field between two streams (for config drift)."""
    from loglens.aggregate import field_value

    def first_value(records):
        for rec in records:
            value = field_value(rec, field)
            if value is not None:
                return value
        return None

    left, right = first_value(before), first_value(after)
    if left == right:
        return {}
    return {field: (left, right)}
