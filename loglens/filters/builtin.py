"""M15 — built-in filter predicates and the Record-to-context bridge."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from loglens.filters.parser import Filter, Node, compile_filter
from loglens.levels import level_order
from loglens.model import Record

# A word whose name collides with a built-in shorthand is compiled to the
# shorthand; explicit `field = value` comparisons are unaffected.


def record_context(record: Record) -> dict[str, Any]:
    """Flatten a Record into a filter evaluation context."""
    context: dict[str, Any] = dict(record.fields)
    context.setdefault("message", record.message)
    context.setdefault("raw", record.raw)
    context.setdefault("level", record.level)
    context.setdefault("timestamp", record.timestamp)
    if record.source is not None:
        context.setdefault("source", record.source)
    return context


class LevelAtLeast:
    """Predicate: record level is at least *threshold* ('error' etc.)."""

    def __init__(self, threshold: str):
        from loglens.levels import normalize_level

        self.threshold = normalize_level(threshold)
        if self.threshold is None:
            raise ValueError(f"unknown level {threshold!r}")
        self._floor = level_order(self.threshold)

    def __call__(self, record: Record) -> bool:
        return level_order(record.level) >= self._floor


class HasField:
    """Predicate: the record carries a non-empty value for *name*."""

    def __init__(self, name: str):
        self.name = name

    def __call__(self, record: Record) -> bool:
        value = record.get(self.name)
        if value is None:
            return False
        return not (isinstance(value, str) and value == "")


class HasTimestamp:
    """Predicate: the record parsed a timestamp."""

    def __call__(self, record: Record) -> bool:
        return record.timestamp is not None


class FromSource:
    """Predicate: the record came from *source* (exact or suffix match)."""

    def __init__(self, source: str):
        self.source = source

    def __call__(self, record: Record) -> bool:
        if record.source is None:
            return False
        return record.source == self.source or record.source.endswith(
            "/" + self.source
        ) or record.source.endswith("\\" + self.source)


class RegexFilter:
    """Predicate: the raw or message text matches a regex."""

    def __init__(self, pattern: str):
        import re

        try:
            self._regex = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc

    def __call__(self, record: Record) -> bool:
        return bool(
            self._regex.search(record.message) or self._regex.search(record.raw)
        )


def matches_filter(record: Record, flt: Filter | str) -> bool:
    """Evaluate *flt* (compiled or source text) against one record."""
    if isinstance(flt, str):
        flt = compile_filter(flt)
    return flt.matches(record_context(record))


def apply_filter(records: Iterable[Record], flt: Filter | str) -> list[Record]:
    """Filter an iterable of records; returns the matching subset."""
    if isinstance(flt, str):
        flt = compile_filter(flt)
    return [rec for rec in records if flt.matches(record_context(rec))]


# --- shorthand names usable inside the expression language ----------------
#
# `level:warn+` style shorthands are expanded before compilation.


def expand_shorthand(text: str) -> str:
    """Expand convenience syntax into plain comparisons.

    ``level:warn+``      -> ``level = warn or level = error or level = critical``
    ``level:error``      -> ``level = error``
    ``has:field``        -> (kept for CLI layer; here returned unchanged)
    """
    import re

    def _level_expand(m: re.Match[str]) -> str:
        name, plus = m.group(1), m.group(2)
        from loglens.levels import CANONICAL_LEVELS, level_order, normalize_level

        target = normalize_level(name)
        if target is None or target not in CANONICAL_LEVELS:
            return m.group(0)
        if plus:
            allowed = [lvl for lvl in CANONICAL_LEVELS if level_order(lvl) >= level_order(target)]
        else:
            allowed = [target]
        return " or ".join(f"level = {lvl}" for lvl in allowed)

    # greedy name, then an optional '+' that must end the token
    return re.sub(r"\blevel:([a-z]+)(\+)?(?![a-z])", _level_expand, text)


def compile_query(text: str) -> Filter:
    """Compile a query with shorthand expansion applied first."""
    return compile_filter(expand_shorthand(text))


def describe(node: Node) -> str:  # pragma: no cover - debug helper
    """Human-readable rendering of an AST (for doctor output)."""
    from loglens.filters.parser import AndNode, CompareNode, NotNode, OrNode, WordNode

    if isinstance(node, OrNode):
        return f"({describe(node.left)} OR {describe(node.right)})"
    if isinstance(node, AndNode):
        return f"({describe(node.left)} AND {describe(node.right)})"
    if isinstance(node, NotNode):
        return f"NOT {describe(node.child)}"
    if isinstance(node, CompareNode):
        return f"{node.field} {node.op} {node.value!r}"
    if isinstance(node, WordNode):
        return f"~{node.word}"
    return repr(node)
