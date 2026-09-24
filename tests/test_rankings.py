"""M18/M19 — top-N and histograms."""

from __future__ import annotations

from loglens.model import Record
from loglens.rankings import (
    field_histogram,
    histogram_ascii,
    latency_profile,
    outliers,
    render_bar,
    top_groups,
)


def rec(fields, **kw):
    return Record(raw="", message=kw.get("message", ""), fields=fields)


class TestTopGroups:
    def test_top_by_count(self):
        records = [rec({"ip": "a"})] * 5 + [rec({"ip": "b"})] * 3 + [rec({"ip": "c"})]
        top = top_groups(records, "ip", n=2)
        assert [g.key for g in top] == ["a", "b"]

    def test_top_by_avg(self):
        records = [
            rec({"ip": "a", "dur": 1}),
            rec({"ip": "a", "dur": 3}),
            rec({"ip": "b", "dur": 100}),
        ]
        top = top_groups(records, "ip", n=1, by="avg:dur")
        assert top[0].key == "b"

    def test_top_by_sum(self):
        records = [
            rec({"ip": "a", "dur": 50}),
            rec({"ip": "b", "dur": 10}),
            rec({"ip": "b", "dur": 20}),
        ]
        top = top_groups(records, "ip", n=1, by="sum:dur")
        # a sums to 50, b sums to 30
        assert top[0].key == "a"

    def test_top_by_max(self):
        records = [
            rec({"ip": "a", "dur": 50}),
            rec({"ip": "b", "dur": 10}),
            rec({"ip": "b", "dur": 99}),
        ]
        top = top_groups(records, "ip", n=1, by="max:dur")
        assert top[0].key == "b"

    def test_unknown_ranking_raises(self):
        import pytest

        with pytest.raises(ValueError):
            top_groups([], "ip", by="banana:x")

    def test_n_larger_than_groups(self):
        records = [rec({"ip": "a"})]
        assert len(top_groups(records, "ip", n=10)) == 1


class TestRenderBar:
    def test_proportional(self):
        assert render_bar(5, 10, width=10) == "#####"

    def test_full(self):
        assert render_bar(10, 10, width=10) == "##########"

    def test_overflow_clamped(self):
        assert render_bar(20, 10, width=10) == "##########"

    def test_zero_max_is_empty(self):
        assert render_bar(5, 0) == ""


class TestHistogram:
    def test_empty_values(self):
        assert histogram_ascii([]) == []

    def test_single_unique_value(self):
        lines = histogram_ascii([7.0])
        assert len(lines) == 1
        assert lines[0].startswith("7 |")

    def test_bins_split_counts(self):
        values = [1.0, 1.1, 9.0, 9.5]
        lines = histogram_ascii(values, bins=10)
        assert len(lines) == 2
        assert lines[0].endswith("2")
        assert lines[1].endswith("2")

    def test_bar_monotonic_in_count(self):
        values = [1.0] * 3 + [5.0]
        lines = histogram_ascii(values, bins=4, width=10)
        counts = [int(line.rsplit(" ", 1)[1]) for line in lines]
        assert counts == [3, 1]

    def test_field_histogram(self):
        records = [rec({"dur": 5}), rec({"dur": 15})]
        lines = field_histogram(records, "dur")
        assert lines

    def test_field_histogram_empty(self):
        assert field_histogram([rec({"a": 1})], "dur") == []


class TestOutliers:
    def test_above_p99(self):
        records = [rec({"dur": i}) for i in range(1, 101)]
        out = outliers(records, "dur", threshold_pct=99)
        # top value(s) above the 99th percentile cutoff
        assert out
        assert all(r.fields["dur"] >= 99 for r in out)

    def test_no_values_no_outliers(self):
        assert outliers([rec({"a": 1})], "dur") == []


class TestLatencyProfile:
    def test_profile_keys(self):
        records = [rec({"dur": i}) for i in range(1, 101)]
        profile = latency_profile(records)
        assert set(profile) == {"mean", "p50", "p95", "p99", "max"}
        assert profile["p50"] == 50
        assert profile["max"] == 100

    def test_empty(self):
        assert latency_profile([], "dur") == {}
