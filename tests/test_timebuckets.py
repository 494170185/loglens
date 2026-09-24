"""M20 — time buckets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loglens.model import Record
from loglens.timebuckets import (
    bucket_counts,
    bucket_records,
    error_rate_series,
    rate_series,
    time_span,
    window_slice,
)


def ts(minute: int, second: int = 0) -> datetime:
    return datetime(2026, 9, 19, 10, minute, second, tzinfo=UTC)


def records_at(*times):
    return [Record(raw="", message="", timestamp=t) for t in times]


class TestBucketing:
    def test_records_sorted_into_minute_buckets(self):
        records = records_at(ts(0, 10), ts(0, 50), ts(1, 5))
        buckets = bucket_records(records, "1m")
        assert len(buckets) == 2
        assert buckets[0].count == 2
        assert buckets[1].count == 1

    def test_gap_buckets_filled_with_zero(self):
        records = records_at(ts(0), ts(5))
        counts = bucket_counts(records, "1m")
        assert len(counts) == 6
        assert counts[1] == (ts(1), 0)

    def test_untimestamped_records_skipped(self):
        records = [Record(raw="", message=""), *records_at(ts(0))]
        buckets = bucket_records(records, "1m")
        assert buckets[0].count == 1

    def test_no_timestamps_gives_empty(self):
        assert bucket_records([Record(raw="", message="")], "1m") == []

    def test_numeric_size_seconds(self):
        records = records_at(ts(0, 0), ts(0, 20), ts(0, 45))
        counts = bucket_counts(records, 30)
        assert counts == [(ts(0, 0), 2), (ts(0, 30), 1)]

    def test_bucket_end_property(self):
        buckets = bucket_records(records_at(ts(0)), "5m")
        assert buckets[0].end == ts(5)

    def test_five_minute_key(self):
        records = records_at(ts(0), ts(4, 59), ts(5, 0))
        buckets = bucket_records(records, "5m")
        assert len(buckets) == 2


class TestRateSeries:
    def test_rate_per_second(self):
        records = records_at(ts(0, 1), ts(0, 2), ts(0, 3))
        rates = rate_series(records, "1m")
        assert rates == [(ts(0), 3 / 60)]


class TestErrorRateSeries:
    def test_5xx_fraction(self):
        def rec_status(status, at):
            return Record(raw="", message="", timestamp=at, fields={"status": status})

        records = [
            rec_status(200, ts(0, 1)),
            rec_status(500, ts(0, 2)),
            rec_status(503, ts(0, 3)),
            rec_status(404, ts(0, 4)),
        ]
        series = error_rate_series(records, "1m")
        assert series == [(ts(0), 0.5)]

    def test_empty_bucket_rate_zero(self):
        records = records_at(ts(0), ts(3))
        series = error_rate_series(records, "1m")
        assert series[1] == (ts(1), 0.0)


class TestWindowSlice:
    def test_inclusive_bounds(self):
        records = records_at(ts(0), ts(1), ts(2))
        out = window_slice(records, ts(0), ts(1))
        assert len(out) == 2

    def test_no_timestamp_excluded(self):
        records = [Record(raw="", message=""), *records_at(ts(0))]
        assert len(window_slice(records, ts(0), ts(5))) == 1


class TestTimeSpan:
    def test_min_max(self):
        records = records_at(ts(5), ts(1), ts(3))
        assert time_span(records) == (ts(1), ts(5))

    def test_none_when_no_timestamps(self):
        assert time_span([Record(raw="", message="")]) is None

    def test_span_with_timedelta_arithmetic(self):
        span = time_span(records_at(ts(0), ts(2)))
        assert span[1] - span[0] == timedelta(minutes=2)
