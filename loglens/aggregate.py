"""M16 — group-by aggregation over record streams."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from loglens.model import Record


def field_value(record: Record, name: str) -> object:
    """Resolve a group-by key, following dotted paths into nested fields."""
    value = record.get(name)
    if value is not None:
        return value
    # dotted path into flattened fields stored by the JSON parser
    if name in record.fields:
        return record.fields[name]
    head, _, rest = name.partition(".")
    if head in record.fields and rest:
        inner = record.fields[head]
        if isinstance(inner, dict):
            return inner.get(rest)
    return None


def render_key(value: object) -> str:
    """Render a group key for display and dict identity."""
    from loglens.parsers.jsonl import render_value

    if value is None:
        return "(missing)"
    if isinstance(value, str):
        return value or "(empty)"
    return render_value(value)


@dataclass
class Group:
    key: str
    records: list[Record] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.records)

    def values(self, name: str) -> list[object]:
        return [field_value(rec, name) for rec in self.records]

    def numeric_values(self, name: str) -> list[float]:
        out = []
        for value in self.values(name):
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

    def first(self, name: str) -> object:
        return field_value(self.records[0], name) if self.records else None


def group_by(
    records: Iterable[Record],
    key: str | Callable[[Record], str],
) -> list[Group]:
    """Group records by a field name or key function; groups keep order of
    first appearance, each sorted by arrival."""
    if isinstance(key, str):
        key_name = key

        def key_fn(rec: Record) -> str:
            return render_key(field_value(rec, key_name))
    else:
        key_fn = key
    buckets: dict[str, list[Record]] = defaultdict(list)
    order: list[str] = []
    for rec in records:
        k = key_fn(rec)
        if k not in buckets:
            order.append(k)
        buckets[k].append(rec)
    return [Group(key=k, records=buckets[k]) for k in order]


def multi_group_by(records: Iterable[Record], keys: tuple[str, ...]) -> list[Group]:
    """Group by the composite of several fields (joined with ' / ')."""
    def composite(rec: Record) -> str:
        parts = [render_key(field_value(rec, name)) for name in keys]
        return " / ".join(parts)

    return group_by(records, composite)


def sort_groups(groups: list[Group], by: str = "count", reverse: bool = True) -> list[Group]:
    """Order groups by 'count' or by a field name ('avg:field' also works)."""
    if by == "count":
        return sorted(groups, key=lambda g: g.count, reverse=reverse)
    if by.startswith("avg:"):
        field_name = by[4:]

        def avg(g: Group) -> float:
            values = g.numeric_values(field_name)
            return sum(values) / len(values) if values else 0.0

        return sorted(groups, key=avg, reverse=reverse)
    field_name = by.strip("first:")

    def first_value(g: Group) -> object:
        return g.first(field_name)

    return sorted(groups, key=lambda g: (str(first_value(g))), reverse=reverse)
