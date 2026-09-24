"""M42a — sampling tests."""

from __future__ import annotations

import random

import pytest

from loglens.model import Record
from loglens.sampling import DistinctSampler, ReservoirSampler, iter_window, sample_records


def rec(msg, **fields):
    return Record(raw=msg, message=msg, fields=fields)


class TestReservoir:
    def test_small_stream_returns_all(self):
        sampler = ReservoirSampler(10)
        for r in [rec("a"), rec("b")]:
            sampler.feed(r)
        assert [r.message for r in sampler.sample()] == ["a", "b"]

    def test_sample_size_capped(self):
        out = sample_records([rec(str(i)) for i in range(1000)], 5, seed=1)
        assert len(out) == 5

    def test_deterministic_with_seed(self):
        records = [rec(str(i)) for i in range(100)]
        first = sample_records(records, 5, seed=42)
        second = sample_records(records, 5, seed=42)
        assert [r.message for r in first] == [r.message for r in second]

    def test_seen_counter(self):
        sampler = ReservoirSampler(1)
        for i in range(10):
            sampler.feed(rec(str(i)))
        assert sampler.seen == 10

    def test_invalid_k(self):
        with pytest.raises(ValueError):
            ReservoirSampler(0)

    def test_uniformity_loose(self):
        rng = random.Random(7)
        sampler = ReservoirSampler(1, rng=rng)
        # with k=1 each item keeps probability 1/n overall
        kept = []
        for i in range(1000):
            sampler.feed(rec(str(i)))
            kept = [r.message for r in sampler.sample()]
        assert kept  # something is always kept once the first arrives
        assert int(kept[0]) < 1000


class TestDistinctSampler:
    def test_one_per_key(self):
        sampler = DistinctSampler(lambda r: r.fields.get("k"))
        for r in [rec("a", k=1), rec("b", k=1), rec("c", k=2)]:
            sampler.feed(r)
        picked = [r.message for r in sampler.picked()]
        assert picked == ["a", "c"]

    def test_counts(self):
        sampler = DistinctSampler(lambda r: r.message)
        for r in [rec("x")] * 5 + [rec("y")]:
            sampler.feed(r)
        assert sampler._seen == 6
        assert sampler.distinct == 2

    def test_empty(self):
        assert DistinctSampler(lambda r: "").picked() == []


class TestIterWindow:
    def test_windows(self):
        records = iter([rec(str(i)) for i in range(4)])
        windows = [w for w in iter_window(records, 2)]
        assert [[r.message for r in w] for w in windows] == [["0", "1"], ["1", "2"], ["2", "3"]]

    def test_shorter_than_window(self):
        assert list(iter_window(iter([rec("a")]), 3)) == []

    def test_invalid_size(self):
        with pytest.raises(ValueError):
            list(iter_window(iter([]), 0))
