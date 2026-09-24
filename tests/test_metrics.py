"""M17 — numeric metrics."""

from __future__ import annotations

import pytest

from loglens.metrics import (
    StatusBreakdown,
    percentile,
    rate_per_second,
    status_breakdown,
    summarize,
    summarize_field,
)
from loglens.model import Record


def rec(fields):
    return Record(raw="", message="", fields=fields)


class TestPercentile:
    def test_nearest_rank(self):
        assert percentile([1, 2, 3, 4, 5], 50) == 3
        assert percentile([1, 2, 3, 4, 5], 95) == 5
        assert percentile([1, 2, 3, 4, 5], 100) == 5

    def test_single_value(self):
        assert percentile([42], 99) == 42

    def test_unsorted_input_ok(self):
        assert percentile([5, 1, 4, 2, 3], 50) == 3

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            percentile([], 50)


class TestSummarize:
    def test_basic_summary(self):
        s = summarize([1.0, 2.0, 3.0, 4.0])
        assert s.count == 4
        assert s.total == 10.0
        assert s.mean == 2.5
        assert s.min == 1.0
        assert s.max == 4.0

    def test_median_and_percentiles(self):
        s = summarize(list(range(1, 101)))
        assert s.median == 50
        assert s.p95 == 95
        assert s.p99 == 99

    def test_stdev_zero_for_constant(self):
        assert summarize([5.0, 5.0, 5.0]).stdev == 0.0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            summarize([])

    def test_as_dict_roundtrip(self):
        d = summarize([1.0, 2.0]).as_dict()
        assert d["count"] == 2
        assert d["total"] == 3.0


class TestSummarizeField:
    def test_mixed_numeric_fields(self):
        records = [rec({"dur": 10}), rec({"dur": "20"}), rec({"dur": "bad"})]
        s = summarize_field(records, "dur")
        assert s is not None
        assert s.count == 2
        assert s.total == 30.0

    def test_no_values_gives_none(self):
        assert summarize_field([rec({"a": 1})], "dur") is None

    def test_bool_excluded(self):
        records = [rec({"ok": True}), rec({"ok": False})]
        assert summarize_field(records, "ok") is None


class TestStatusBreakdown:
    def test_counts_and_classes(self):
        records = [
            rec({"status": 200}),
            rec({"status": 200}),
            rec({"status": 404}),
            rec({"status": 500}),
        ]
        bd = status_breakdown(records)
        assert bd.counts[200] == 2
        assert bd.class_counts["2xx"] == 2
        assert bd.class_counts["4xx"] == 1
        assert bd.class_counts["5xx"] == 1

    def test_string_statuses_coerced(self):
        records = [rec({"status": "503"})]
        assert status_breakdown(records).counts[503] == 1

    def test_error_rate(self):
        records = [rec({"status": 200})] * 3 + [rec({"status": 500})]
        assert status_breakdown(records).error_rate() == 0.25

    def test_empty(self):
        bd = status_breakdown([])
        assert isinstance(bd, StatusBreakdown)
        assert bd.total == 0
        assert bd.error_rate() == 0.0

    def test_missing_status_ignored(self):
        assert status_breakdown([rec({"other": 1})]).total == 0


class TestRate:
    def test_simple(self):
        assert rate_per_second(10, 2) == 5.0

    def test_zero_window(self):
        assert rate_per_second(10, 0) == 0.0
