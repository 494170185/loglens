"""M42a — reservoir sampling for large streams."""

from __future__ import annotations

import random
from collections.abc import Iterable, Iterator

from loglens.model import Record


class ReservoirSampler:
    """Keep a uniform random sample of *k* items from a stream of unknown size.

    Classic algorithm V: each item survives with probability k/i at
    position i, giving every item an equal k/n chance in a stream of n.
    """

    def __init__(self, k: int, rng: random.Random | None = None):
        if k <= 0:
            raise ValueError("sample size must be positive")
        self.k = k
        self.rng = rng or random.Random()
        self.reservoir: list[Record] = []
        self._seen = 0

    @property
    def seen(self) -> int:
        return self._seen

    def feed(self, record: Record) -> None:
        self._seen += 1
        if len(self.reservoir) < self.k:
            self.reservoir.append(record)
            return
        slot = self.rng.randrange(self._seen)
        if slot < self.k:
            self.reservoir[slot] = record

    def sample(self) -> list[Record]:
        return list(self.reservoir)


def sample_records(
    records: Iterable[Record],
    k: int,
    seed: int | None = None,
) -> list[Record]:
    """Convenience wrapper: sample *k* records uniformly."""
    rng = random.Random(seed) if seed is not None else None
    sampler = ReservoirSampler(k, rng=rng)
    for rec in records:
        sampler.feed(rec)
    return sampler.sample()


class DistinctSampler:
    """Sample at most one record per distinct key, in first-seen order.

    Useful for 'show me one example of each error message' over huge logs
    without holding every distinct record in memory.
    """

    def __init__(self, key_fn):
        self.key_fn = key_fn
        self._keys: set[str] = set()
        self._picked: list[Record] = []
        self._seen = 0

    def feed(self, record: Record) -> bool:
        """Add the record if its key is new; returns True when kept."""
        self._seen += 1
        key = str(self.key_fn(record))
        if key in self._keys:
            return False
        self._keys.add(key)
        self._picked.append(record)
        return True

    def picked(self) -> list[Record]:
        return list(self._picked)

    @property
    def distinct(self) -> int:
        return len(self._picked)


def iter_window(records: Iterator[Record], size: int) -> Iterator[list[Record]]:
    """Yield overlapping windows of *size* consecutive records."""
    if size <= 0:
        raise ValueError("window size must be positive")
    window: list[Record] = []
    for rec in records:
        window.append(rec)
        if len(window) > size:
            window.pop(0)
        if len(window) == size:
            yield list(window)
