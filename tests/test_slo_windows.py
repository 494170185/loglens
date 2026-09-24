"""M42f — tests for SLO and window index."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.model import Record
from loglens.slo import error_budget, evaluate_slo
from loglens.windows import (
    Window,
    WindowIndex,
    gaps_between,
    tag_records_with_windows,
)


def rec(fields, stamp=None):
    return Record(raw="", message="", fields=fields, timestamp=stamp)


def ts(minute=0, second=0):
    return datetime(2026, 9, 19, 10, minute, second, tzinfo=UTC)


class TestSlo:
    def test_full_compliance(self):
        records = [rec({"status": 200, "dur": 50})] * 10
        result = evaluate_slo(records)
        assert result.ok
        assert result.availability == 1.0
        assert result.latency_compliance == 1.0

    def test_availability_drop(self):
        records = [rec({"status": 200})] * 99 + [rec({"status": 500})]
        result = evaluate_slo(records)
        assert result.availability == pytest_approx(0.99)
        assert result.ok  # exactly at the boundary

    def test_latency_miss(self):
        records = [rec({"status": 200, "dur": 5000})]
        result = evaluate_slo(records)
        assert not result.ok

    def test_no_status_defaults_ok(self):
        result = evaluate_slo([rec({"msg": "x"})])
        assert result.availability == 1.0

    def test_custom_budget(self):
        records = [rec({"dur": 1500})]
        assert evaluate_slo(records, latency_budget_ms=2000).latency_compliance == 1.0
        assert evaluate_slo(records, latency_budget_ms=1000).latency_compliance == 0.0


def pytest_approx(value):
    import pytest

    return pytest.approx(value)


class TestErrorBudget:
    def test_healthy(self):
        records = [rec({"status": 200})] * 100
        assert error_budget(records) == 1.0

    def test_burned(self):
        records = [rec({"status": 200})] * 99 + [rec({"status": 503})]
        budget = error_budget(records, target_availability=0.99)
        assert abs(budget) < 1e-9  # exactly consumed

    def test_blowout(self):
        records = [rec({"status": 500})] * 10
        assert error_budget(records) < 0

    def test_empty(self):
        assert error_budget([]) == 1.0


class TestWindowIndex:
    def test_covering(self):
        windows = [
            Window(ts(0), ts(10), "deploy"),
            Window(ts(20), ts(30), "incident"),
        ]
        index = WindowIndex(windows)
        assert index.first_covering(ts(5)).label == "deploy"
        assert index.first_covering(ts(25)).label == "incident"
        assert index.first_covering(ts(15)) is None

    def test_overlapping_windows_both_returned(self):
        windows = [
            Window(ts(0), ts(15), "a"),
            Window(ts(10), ts(20), "b"),
        ]
        index = WindowIndex(windows)
        hits = index.covering(ts(12))
        assert {w.label for w in hits} == {"a", "b"}

    def test_total_coverage_merges(self):
        windows = [
            Window(ts(0), ts(10)),
            Window(ts(5), ts(20)),
            Window(ts(30), ts(40)),
        ]
        # merged: 00:00-20:00 (1200s) + 30:00-40:00 (600s)
        assert WindowIndex(windows).total_coverage_seconds() == 1800.0

    def test_disjoint_windows_not_merged(self):
        windows = [Window(ts(0), ts(5)), Window(ts(10), ts(15))]
        assert WindowIndex(windows).total_coverage_seconds() == 600.0

    def test_contains_boundary(self):
        w = Window(ts(0), ts(10))
        assert w.contains(ts(0))
        assert not w.contains(ts(10))

    def test_duration(self):
        assert Window(ts(0), ts(10)).duration_seconds() == 600.0


class TestTagging:
    def test_counts_per_label(self):
        windows = [Window(ts(0), ts(10), "a"), Window(ts(10), ts(20), "b")]
        records = [
            rec({}, ts(1)),
            rec({}, ts(2)),
            rec({}, ts(11)),
            rec({}, ts(15)),
            rec({}),  # no timestamp -> ignored
        ]
        counts = tag_records_with_windows(records, WindowIndex(windows))
        assert counts == {"a": 2, "b": 2}


class TestGaps:
    def test_gap_found(self):
        windows = [Window(ts(0), ts(10)), Window(ts(30), ts(40))]
        gaps = gaps_between(windows)
        assert len(gaps) == 1
        assert gaps[0] == (ts(10), ts(30))

    def test_no_gap_when_touching(self):
        windows = [Window(ts(0), ts(10)), Window(ts(10), ts(20))]
        assert gaps_between(windows) == []

    def test_single_window(self):
        assert gaps_between([Window(ts(0), ts(10))]) == []
