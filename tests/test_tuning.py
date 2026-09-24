"""M42h — tuning helpers tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loglens.model import Record
from loglens.tuning import (
    level_mix,
    noisiest_hours,
    suggest_burst_threshold,
    suggest_silence_threshold,
    suggest_z_threshold,
)


def rec(msg="", level=None, stamp=None):
    return Record(raw=msg, message=msg, level=level, timestamp=stamp)


def ts(hours, minutes=0):
    return datetime(2026, 9, 19, hours, minutes, 0, tzinfo=UTC)


class TestBurstThreshold:
    def test_low_diversity_raises_bar(self):
        records = [rec("same")] * 100
        assert suggest_burst_threshold(records) >= 10

    def test_high_diversity_keeps_minimum(self):
        records = [rec(f"unique {i}") for i in range(100)]
        assert suggest_burst_threshold(records) == 3

    def test_empty_stream_default(self):
        assert suggest_burst_threshold([]) == 5


class TestSilenceThreshold:
    def test_regular_stream(self):
        base = ts(0)
        records = [
            rec(stamp=base + timedelta(seconds=i * 10)) for i in range(20)
        ]
        threshold = suggest_silence_threshold(records)
        # 10s median * factor 10 = ~100s, floored at 60
        assert 60 <= threshold <= 300

    def test_sparse_stream_uses_floor(self):
        records = [rec(stamp=ts(0)), rec(stamp=ts(12))]
        assert suggest_silence_threshold(records) == 300.0

    def test_too_few_stamps(self):
        assert suggest_silence_threshold([rec(stamp=ts(0))]) == 300.0


class TestZThreshold:
    def test_small_series_default(self):
        records = [rec() for _ in range(5)]
        # no field values: below 30 samples -> default
        assert suggest_z_threshold(records, "dur") == 3.0

    def test_fp_rate_table(self):
        records = [rec() for _ in range(50)]
        from loglens.model import Record as R

        records = [R(raw="", message="", fields={"dur": i}) for i in range(50)]
        assert suggest_z_threshold(records, "dur", false_positive_rate=0.01) == 2.576
        assert suggest_z_threshold(records, "dur", false_positive_rate=0.05) == 1.96


class TestLevelMix:
    def test_fractions(self):
        records = [rec(level="error")] * 3 + [rec(level="info")]
        mix = level_mix(records)
        assert mix == {"error": 0.75, "info": 0.25}

    def test_no_levels(self):
        assert level_mix([rec(), rec()]) == {}


class TestNoisiestHours:
    def test_top_hours(self):
        records = [rec(stamp=ts(9))] * 10 + [rec(stamp=ts(14))] * 5
        top = noisiest_hours(records, top=2)
        assert top[0] == (9, 10)
        assert top[1] == (14, 5)

    def test_unstamped_ignored(self):
        assert noisiest_hours([rec()]) == []
