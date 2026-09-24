"""M22 — rate shift and spike detection."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.model import Record
from loglens.shifts import Shift, detect_shifts, detect_spikes, summarize_shifts


def ts(minute: int) -> datetime:
    return datetime(2026, 9, 19, 10, minute, 0, tzinfo=UTC)


def records_at_minutes(minutes):
    return [Record(raw="", message="", timestamp=ts(m)) for m in minutes]


class TestDetectShifts:
    def test_traffic_spike_detected(self):
        # 3 events in minute 0, 9 in minute 1 (x3)
        records = records_at_minutes([0, 0, 0] + [1] * 9)
        shifts = detect_shifts(records, "1m", min_ratio=3.0)
        assert len(shifts) == 1
        assert shifts[0].direction == "spike"
        assert shifts[0].ratio >= 3.0

    def test_traffic_drop_detected(self):
        records = records_at_minutes([0] * 9 + [1] * 3)
        shifts = detect_shifts(records, "1m", min_ratio=3.0)
        assert len(shifts) == 1
        assert shifts[0].direction == "drop"

    def test_steady_traffic_no_shifts(self):
        records = records_at_minutes([0] * 5 + [1] * 5 + [2] * 5)
        assert detect_shifts(records, "1m") == []

    def test_min_count_guards_noise(self):
        # 1 event then 10: small side has fewer than 3 events
        records = records_at_minutes([0] + [1] * 10)
        assert detect_shifts(records, "1m", min_count=3) == []

    def test_shift_at_metadata(self):
        records = records_at_minutes([0] * 4 + [1] * 12)
        shifts = detect_shifts(records, "1m")
        assert shifts[0].at == ts(1)
        assert shifts[0].before < shifts[0].after


class TestDetectSpikes:
    def test_single_bucket_spike(self):
        minutes = [0] * 4 + [1] * 4 + [2] * 40 + [3] * 4 + [4] * 4
        records = records_at_minutes(minutes)
        spikes = detect_spikes(records, "1m", factor=5.0)
        assert len(spikes) == 1
        assert spikes[0].at == ts(2)
        assert spikes[0].factor >= 5.0

    def test_no_spikes_in_flat_traffic(self):
        records = records_at_minutes([0] * 5 + [1] * 5 + [2] * 5)
        assert detect_spikes(records, "1m") == []

    def test_too_few_buckets(self):
        assert detect_spikes(records_at_minutes([0, 1])) == []

    def test_zero_baseline_ignored(self):
        # neighbors are zero -> baseline 0 -> not a reportable spike
        records = records_at_minutes([0] * 5 + [2] * 5)
        assert detect_spikes(records, "1m") == []


class TestSummarize:
    def test_empty(self):
        assert summarize_shifts([]) == "no rate shifts detected"

    def test_rendering(self):
        shift = Shift(
            at=ts(1),
            before=0.05,
            after=0.2,
            ratio=4.0,
        )
        text = summarize_shifts([shift])
        assert "10:01" in text
        assert "up" in text
        assert "x4.0" in text

    def test_drop_rendering(self):
        shift = Shift(at=ts(2), before=0.2, after=0.05, ratio=0.25)
        assert "down" in summarize_shifts([shift])
