"""M29/M30 — anomalies and silence gaps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loglens.anomalies import (
    Anomaly,
    FreshnessReport,
    Silence,
    detect_anomalies,
    detect_silences,
    freshness,
    gap_windows,
    long_running,
)
from loglens.model import Record


def rec(fields, ts=None):
    return Record(raw="", message="", fields=fields, timestamp=ts)


def ts(minute):
    if minute >= 60:
        return datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    return datetime(2026, 9, 19, 10, minute, 0, tzinfo=UTC)


class TestDetectAnomalies:
    def test_outlier_found(self):
        values = [10.0] * 20 + [1000.0]
        records = [rec({"dur": v}) for v in values]
        anomalies = detect_anomalies(records, "dur", min_z=3.0)
        assert len(anomalies) == 1
        assert anomalies[0].value == 1000.0
        assert anomalies[0].zscore >= 3.0

    def test_uniform_values_no_anomalies(self):
        records = [rec({"dur": 5}) for _ in range(10)]
        assert detect_anomalies(records, "dur") == []

    def test_too_few_values(self):
        records = [rec({"dur": 1}), rec({"dur": 100})]
        assert detect_anomalies(records, "dur") == []

    def test_negative_zscore_anomaly(self):
        values = [100.0] * 20 + [1.0]
        records = [rec({"dur": v}) for v in values]
        anomalies = detect_anomalies(records, "dur", min_z=3.0)
        assert len(anomalies) == 1
        assert anomalies[0].zscore <= -3.0

    def test_anomaly_carries_record(self):
        values = [10.0] * 30 + [900.0]
        records = [rec({"dur": v}) for v in values]
        anomalies = detect_anomalies(records, "dur")
        assert anomalies
        assert isinstance(anomalies[0], Anomaly)
        assert anomalies[0].record.fields["dur"] == 900.0

    def test_non_numeric_ignored(self):
        records = [rec({"dur": 10}), rec({"dur": "x"}), rec({"dur": 10}), rec({"dur": 10})]
        assert detect_anomalies(records, "dur") == []


class TestDetectSilences:
    def test_five_minute_gap_detected(self):
        records = [rec({}, ts(0)), rec({}, ts(10))]
        silences = detect_silences(records, min_seconds=300)
        assert len(silences) == 1
        assert silences[0].seconds == 600
        assert silences[0].minutes == 10.0

    def test_small_gap_ignored(self):
        records = [rec({}, ts(0)), rec({}, ts(2))]
        assert detect_silences(records, min_seconds=300) == []

    def test_multiple_gaps(self):
        records = [rec({}, ts(0)), rec({}, ts(20)), rec({}, ts(21)), rec({}, ts(50))]
        silences = detect_silences(records, min_seconds=300)
        assert len(silences) == 2

    def test_unsorted_input_handled(self):
        records = [rec({}, ts(50)), rec({}, ts(0)), rec({}, ts(20))]
        assert len(detect_silences(records, min_seconds=300)) == 2

    def test_no_timestamps(self):
        assert detect_silences([rec({})], min_seconds=1) == []

    def test_single_record(self):
        assert detect_silences([rec({}, ts(0))]) == []

    def test_silence_type(self):
        records = [rec({}, ts(0)), rec({}, ts(30))]
        s = detect_silences(records, min_seconds=300)[0]
        assert isinstance(s, Silence)
        assert s.start < s.end


class TestFreshness:
    def test_fresh(self):
        now = ts(10)
        records = [rec({}, ts(9))]
        report = freshness(records, now)
        assert report.age_seconds == 60
        assert not report.is_stale

    def test_stale_over_an_hour(self):
        now = ts(70)
        records = [rec({}, ts(0))]
        report = freshness(records, now)
        assert report.is_stale

    def test_no_data_is_stale(self):
        report = freshness([], ts(0))
        assert isinstance(report, FreshnessReport)
        assert report.is_stale

    def test_last_seen_is_max(self):
        now = ts(100)
        records = [rec({}, ts(5)), rec({}, ts(50)), rec({}, ts(10))]
        assert freshness(records, now).last_seen == ts(50)


class TestLongRunning:
    def test_threshold_filter(self):
        records = [rec({"dur": 500}), rec({"dur": 2000}), rec({"dur": 5000})]
        out = long_running(records, "dur", threshold=1000)
        assert len(out) == 2


class TestGapWindows:
    def test_widening(self):
        silence = Silence(start=ts(10), end=ts(20), seconds=600)
        windows = gap_windows([silence], width=timedelta(minutes=1))
        start, end = windows[0]
        assert start == ts(9)
        assert end == ts(21)

    def test_no_width_passthrough(self):
        silence = Silence(start=ts(10), end=ts(20), seconds=600)
        assert gap_windows([silence]) == [(ts(10), ts(20))]
