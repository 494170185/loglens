"""M40 — composable streaming pipeline over record iterators."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from loglens.model import Record

Stage = Callable[[Iterator[Record]], Iterator[Record]]


class Pipeline:
    """Chain stages that each consume and produce a record stream.

    Stages are lazy: nothing runs until the pipeline is iterated, so a
    file is read at most once no matter how many stages follow.
    """

    def __init__(self, stages: list[Stage] | None = None):
        self.stages: list[Stage] = list(stages or [])

    def add(self, stage: Stage) -> Pipeline:
        self.stages.append(stage)
        return self

    def then(self, stage: Stage) -> Pipeline:
        return self.add(stage)

    def run(self, source: Iterable[Record]) -> list[Record]:
        return list(self.iter(source))

    def iter(self, source: Iterable[Record]) -> Iterator[Record]:
        stream: Iterator[Record] = iter(source)
        for stage in self.stages:
            stream = stage(stream)
        yield from stream


def stage_filter(predicate: Callable[[Record], bool]) -> Stage:
    """Keep only records matching *predicate*."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for rec in stream:
            if predicate(rec):
                yield rec

    return apply


def stage_limit(n: int) -> Stage:
    """Pass through at most *n* records, then stop pulling."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for _i, rec in enumerate(stream):
            if _i >= n:
                return
            yield rec

    return apply


def stage_offset(n: int) -> Stage:
    """Skip the first *n* records."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for i, rec in enumerate(stream):
            if i >= n:
                yield rec

    return apply


def stage_map(transform: Callable[[Record], Record]) -> Stage:
    """Apply *transform* to every record."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for rec in stream:
            yield transform(rec)

    return apply


def stage_dedup(key: Callable[[Record], str]) -> Stage:
    """Drop records whose key was already seen."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        seen: set[str] = set()
        for rec in stream:
            k = key(rec)
            if k in seen:
                continue
            seen.add(k)
            yield rec

    return apply


def stage_min_level(level: str) -> Stage:
    """Keep records at or above a severity threshold."""
    from loglens.levels import level_order, normalize_level

    target = normalize_level(level)
    floor = level_order(target)

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for rec in stream:
            if level_order(rec.level) >= floor:
                yield rec

    return apply


def stage_sample_every(n: int) -> Stage:
    """Keep every *n*-th record (1 = all)."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for i, rec in enumerate(stream):
            if i % n == 0:
                yield rec

    return apply


@dataclass
class PipelineStats:
    """Counters collected by the ``stats`` stage."""

    seen: int = 0
    passed: int = 0
    dropped: int = 0
    by_level: dict[str, int] = field(default_factory=dict)


def stage_stats(stats: PipelineStats) -> Stage:
    """Count everything that flows through into *stats*."""

    def apply(stream: Iterator[Record]) -> Iterator[Record]:
        for rec in stream:
            stats.seen += 1
            stats.passed += 1
            if rec.level:
                stats.by_level[rec.level] = stats.by_level.get(rec.level, 0) + 1
            yield rec

    return apply
