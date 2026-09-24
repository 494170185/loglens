"""M42c — declarative rule packs over records (reusable detections)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from loglens.model import Record

Predicate = Callable[[Record], bool]


@dataclass
class Rule:
    """One named detection with a severity and a predicate."""

    name: str
    description: str
    severity: str  # info | warning | critical
    predicate: Predicate
    hits: list[Record] = field(default_factory=list, repr=False)

    def check(self, record: Record) -> bool:
        if self.predicate(record):
            self.hits.append(record)
            return True
        return False


def field_equals(name: str, value: object) -> Predicate:
    def check(record: Record) -> bool:
        return record.get(name) == value

    return check


def field_above(name: str, threshold: float) -> Predicate:
    def check(record: Record) -> bool:
        value = record.get(name)
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value > threshold

    return check


def field_below(name: str, threshold: float) -> Predicate:
    def check(record: Record) -> bool:
        value = record.get(name)
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value < threshold

    return check


def message_contains(needle: str) -> Predicate:
    def check(record: Record) -> bool:
        return needle.lower() in (record.message or record.raw).lower()

    return check


def any_of(*predicates: Predicate) -> Predicate:
    def check(record: Record) -> bool:
        return any(p(record) for p in predicates)

    return check


def all_of(*predicates: Predicate) -> Predicate:
    def check(record: Record) -> bool:
        return all(p(record) for p in predicates)

    return check


class RulePack:
    """A bundle of rules evaluated together over a stream."""

    def __init__(self, name: str):
        self.name = name
        self.rules: list[Rule] = []

    def add(self, name: str, description: str, severity: str, predicate: Predicate) -> Rule:
        rule = Rule(name=name, description=description, severity=severity, predicate=predicate)
        self.rules.append(rule)
        return rule

    def evaluate(self, records: list[Record]) -> list[Rule]:
        for record in records:
            for rule in self.rules:
                rule.check(record)
        return [r for r in self.rules if r.hits]


def default_pack() -> RulePack:
    """The shipped starter pack of common log detections."""
    pack = RulePack("default")
    pack.add(
        "server-error", "5xx responses", "critical",
        field_above("status", 499.5),
    )
    pack.add(
        "client-error", "4xx responses", "warning",
        all_of(field_above("status", 399.5), field_below("status", 500)),
    )
    pack.add(
        "slow-request", "requests over a second", "warning",
        field_above("duration_ms", 1000),
    )
    pack.add(
        "out-of-memory", "OOM mentions", "critical",
        message_contains("out of memory"),
    )
    return pack
