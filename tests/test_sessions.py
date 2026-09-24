"""M31 — sessionization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loglens.model import Record
from loglens.sessions import (
    Session,
    longest_sessions,
    session_durations,
    sessionize,
)


def ts(minutes, seconds=0):
    return datetime(2026, 9, 19, 10, minutes, seconds, tzinfo=UTC)


def rec(client, minute, seconds=0, **fields):
    return Record(
        raw="", message="", timestamp=ts(minute, seconds), fields={"client": client, **fields}
    )


class TestSessionize:
    def test_single_session(self):
        records = [rec("a", 0), rec("a", 5), rec("a", 10)]
        sessions = sessionize(records)
        assert len(sessions) == 1
        assert sessions[0].count == 3

    def test_two_clients_two_sessions(self):
        records = [rec("a", 0), rec("b", 1), rec("a", 2)]
        sessions = sessionize(records)
        assert len(sessions) == 2
        assert {s.key for s in sessions} == {"a", "b"}

    def test_idle_timeout_splits(self):
        # a active at 10:00 and 10:40 -> two sessions under a 30m timeout
        records = [rec("a", 0), rec("a", 40)]
        sessions = sessionize(records, idle_timeout=timedelta(minutes=30))
        assert len(sessions) == 2

    def test_within_timeout_keeps_session(self):
        records = [rec("a", 0), rec("a", 29)]
        sessions = sessionize(records, idle_timeout=timedelta(minutes=30))
        assert len(sessions) == 1

    def test_missing_key_skipped(self):
        records = [rec("a", 0), Record(raw="", message="")]
        assert len(sessionize(records)) == 1

    def test_untimestamped_attaches_to_current(self):
        mixed = [
            rec("a", 0),
            Record(raw="", message="", fields={"client": "a"}),
        ]
        sessions = sessionize(mixed)
        assert sessions[0].count == 2

    def test_custom_key_field(self):
        records = [
            Record(raw="", message="", timestamp=ts(0), fields={"user": "u1"}),
            Record(raw="", message="", timestamp=ts(1), fields={"user": "u1"}),
        ]
        sessions = sessionize(records, key_field="user")
        assert sessions[0].key == "u1"


class TestSessionProperties:
    def test_start_end_duration(self):
        records = [rec("a", 0), rec("a", 10, 30)]
        s = sessionize(records)[0]
        assert s.start == ts(0)
        assert s.end == ts(10, 30)
        assert s.duration == timedelta(minutes=10, seconds=30)

    def test_summary_line(self):
        s = sessionize([rec("a", 0), rec("a", 1)])[0]
        line = s.summary_line()
        assert "a" in line
        assert "10:00:00" in line and "10:01:00" in line

    def test_events(self):
        records = [rec("a", 0, status=200), rec("a", 1, status=500)]
        s = sessionize(records)[0]
        assert s.events("status") == [200, 500]

    def test_no_timestamps_session_props(self):
        s = Session(key="x", records=[Record(raw="", message="", fields={"client": "x"})])
        assert s.start is None
        assert s.duration is None


class TestSessionStats:
    def test_durations(self):
        records = [*[rec("a", 0), rec("a", 10)], *[rec("b", 0), rec("b", 2)]]
        sessions = sessionize(records)
        assert sorted(session_durations(sessions)) == [120.0, 600.0]

    def test_longest_sessions(self):
        records = [rec("a", 0)] * 10 + [rec("b", 1)] * 3
        sessions = sessionize(records)
        top = longest_sessions(sessions, top=1)
        assert top[0].key == "a"
        assert top[0].count == 10
