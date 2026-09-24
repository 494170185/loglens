"""M42b — correlation tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loglens.correlate import co_occurrence, correlate_streams, join_by_field
from loglens.model import Record


def ts(seconds):
    return datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=seconds)


def rec(fields=None, stamp=None):
    return Record(raw="", message="", fields=fields or {}, timestamp=stamp)


class TestCorrelateStreams:
    def test_close_events_matched(self):
        left = [rec({"msg": "error"}, ts(10))]
        right = [rec({"msg": "deploy"}, ts(11))]
        out = correlate_streams(left, right, within_seconds=2)
        assert len(out) == 1
        assert out[0].delta_seconds == 1.0

    def test_outside_window_not_matched(self):
        left = [rec({}, ts(10))]
        right = [rec({}, ts(20))]
        assert correlate_streams(left, right, within_seconds=2) == []

    def test_unsorted_inputs_ok(self):
        left = [rec({}, ts(20)), rec({}, ts(10))]
        right = [rec({}, ts(11))]
        out = correlate_streams(left, right, within_seconds=2)
        assert len(out) == 1

    def test_each_right_matches_once(self):
        left = [rec({"id": 1}, ts(10)), rec({"id": 2}, ts(10))]
        right = [rec({}, ts(10))]
        out = correlate_streams(left, right, within_seconds=1)
        assert len(out) == 1

    def test_untimestamped_skipped(self):
        assert correlate_streams([rec({})], [rec({}, ts(0))]) == []


class TestJoinByField:
    def test_inner_join(self):
        left = [rec({"req": "r1", "side": "access"})]
        right = [rec({"req": "r1", "side": "app"})]
        pairs = join_by_field(left, right, "req")
        assert len(pairs) == 1
        assert pairs[0][0].fields["side"] == "access"
        assert pairs[0][1].fields["side"] == "app"

    def test_no_match(self):
        assert join_by_field([rec({"req": "a"})], [rec({"req": "b"})], "req") == []

    def test_multiple_matches(self):
        left = [rec({"req": "x", "n": 1}), rec({"req": "x", "n": 2})]
        right = [rec({"req": "x"})]
        assert len(join_by_field(left, right, "req")) == 2


class TestCoOccurrence:
    def test_counts_pairs(self):
        records = [
            rec({"status": 500, "host": "a"}),
            rec({"status": 500, "host": "a"}),
            rec({"status": 200, "host": "b"}),
        ]
        counts = co_occurrence(records, "status", "host")
        assert counts == {("500", "a"): 2, ("200", "b"): 1}

    def test_missing_field_skipped(self):
        assert co_occurrence([rec({"status": 500})], "status", "host") == {}
