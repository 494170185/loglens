"""M42e — tests for sparklines and field inventory."""

from __future__ import annotations

import pytest

from loglens.fields import field_inventory, numeric_fields, value_histogram
from loglens.model import Record
from loglens.sparklines import series_summary, sparkline, trend_arrow


def rec(fields, **kw):
    return Record(raw="", message="", fields=fields, **kw)


class TestSparkline:
    def test_empty(self):
        assert sparkline([]) == ""

    def test_flat_series_low_block(self):
        out = sparkline([5, 5, 5], width=3)
        assert out == "▁▁▁"

    def test_rising_series(self):
        out = sparkline([0, 5, 10], width=3)
        assert out[0] == "▁"
        assert out[-1] == "█"

    def test_width_downsample(self):
        out = sparkline(list(range(100)), width=10)
        assert len(out) == 10

    def test_width_upsample(self):
        out = sparkline([1, 2], width=6)
        assert len(out) == 6

    def test_invalid_width(self):
        with pytest.raises(ValueError):
            sparkline([1], width=0)

    def test_trend_arrows(self):
        assert trend_arrow([1, 2, 3]) == "↗"
        assert trend_arrow([3, 2, 1]) == "↘"
        assert trend_arrow([2, 2, 2]) == "→"
        assert trend_arrow([1]) == "→"

    def test_series_summary(self):
        assert series_summary([1, 2, 3]) == "1/2/3"
        assert series_summary([]) == "-"


class TestFieldInventory:
    def test_coverage_sorted(self):
        records = [
            rec({"a": 1, "b": 2}),
            rec({"a": 1}),
            rec({"a": 1}),
        ]
        stats = field_inventory(records)
        assert stats[0].name == "a"
        assert stats[0].coverage == 1.0
        assert stats[1].name == "b"
        assert stats[1].coverage == pytest.approx(1 / 3)

    def test_sparse_flag(self):
        stats = field_inventory([rec({"rare": 1})] + [rec({})] * 20)
        rare = next(s for s in stats if s.name == "rare")
        assert rare.is_sparse

    def test_empty_stream(self):
        assert field_inventory([]) == []

    def test_builtins_excluded_by_default(self):
        records = [Record(raw="", message="", level="error")]
        names = [s.name for s in field_inventory(records)]
        assert "level" not in names
        assert "level" in [s.name for s in field_inventory(records, include_builtins=True)]


class TestValueHistogram:
    def test_top_values(self):
        records = [rec({"s": "500"})] * 3 + [rec({"s": "404"})]
        assert value_histogram(records, "s") == [("500", 3), ("404", 1)]

    def test_top_limit(self):
        records = [rec({"k": str(i)}) for i in range(20)]
        assert len(value_histogram(records, "k", top=3)) == 3

    def test_missing_ignored(self):
        assert value_histogram([rec({})], "k") == []


class TestNumericFields:
    def test_detects_numeric_only(self):
        records = [rec({"n": 5, "s": "x", "f": 1.5})]
        assert numeric_fields(records) == ["f", "n"]

    def test_bool_excluded(self):
        assert numeric_fields([rec({"ok": True})]) == []
