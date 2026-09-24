"""M28 — repeat-burst detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loglens.bursts import Burst, detect_bursts, message_frequency, normalize_message
from loglens.model import Record


def rec(message, **kw):
    stamp = kw.pop("timestamp", None)
    line = kw.pop("line_no", None)
    return Record(raw=message, message=message, timestamp=stamp, line_no=line)


class TestNormalize:
    def test_ips_collapsed(self):
        assert normalize_message("connect from 10.0.0.1 failed") == (
            normalize_message("connect from 10.0.0.2 failed")
        )

    def test_numbers_collapsed(self):
        assert normalize_message("retry 3 in 200ms") == normalize_message(
            "retry 7 in 900ms"
        )

    def test_uuids_collapsed(self):
        a = normalize_message("request 550e8400-e29b-41d4-a716-446655440000 done")
        b = normalize_message("request 12345678-1234-1234-1234-123456789012 done")
        assert a == b

    def test_case_insensitive(self):
        assert normalize_message("TIMEOUT") == normalize_message("timeout")


class TestDetectBursts:
    def test_simple_burst(self):
        records = [
            rec("timeout waiting for db", timestamp=datetime(2026, 9, 19, 10, 0, i, tzinfo=UTC))
            for i in range(6)
        ]
        bursts = detect_bursts(records, min_repeat=5)
        assert len(bursts) == 1
        assert bursts[0].count == 6

    def test_variable_values_still_burst(self):
        records = [rec(f"timeout after {i}ms") for i in range(8)]
        bursts = detect_bursts(records, min_repeat=5)
        assert len(bursts) == 1
        assert bursts[0].count == 8

    def test_different_messages_no_burst(self):
        records = [rec(f"event number {i}") for i in range(10)]
        # numbers normalize away, so these all share a signature... which
        # means this IS a burst by design; use truly distinct text instead
        records = [rec(f"distinct event {chr(97 + i)}", timestamp=None) for i in range(6)]
        assert detect_bursts(records, min_repeat=5) == []

    def test_below_threshold_ignored(self):
        records = [rec("same message")] * 4
        assert detect_bursts(records, min_repeat=5) == []

    def test_burst_metadata(self):
        base = datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC)
        records = [
            rec("boom", timestamp=base + timedelta(seconds=i), line_no=i + 1)
            for i in range(5)
        ]
        burst = detect_bursts(records, min_repeat=5)[0]
        assert isinstance(burst, Burst)
        assert burst.first_line == 1
        assert burst.duration_seconds == 4.0
        assert burst.example == "boom"

    def test_two_bursts_separated(self):
        records = (
            [rec("err a")] * 5 + [rec("middle")] + [rec("err b")] * 5
        )
        bursts = detect_bursts(records, min_repeat=5)
        assert len(bursts) == 2

    def test_empty_input(self):
        assert detect_bursts([], min_repeat=5) == []


class TestMessageFrequency:
    def test_ranking(self):
        records = [rec("x")] * 3 + [rec("y")] + [rec("z")] * 2
        freq = message_frequency(records)
        assert freq[0] == ("x", 3)
        assert freq[1] == ("z", 2)

    def test_top_limit(self):
        records = [rec(f"msg {chr(97 + i)}") for i in range(20)]
        assert len(message_frequency(records, top=5)) == 5
