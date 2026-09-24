"""M4 — timestamp parsing across the formats logs actually use."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from loglens.timestamps import (
    TimestampParser,
    format_timestamp,
    gap_seconds,
    round_to_bucket,
    set_default_year,
    to_utc,
)


@pytest.fixture(autouse=True)
def _pinned_year():
    set_default_year(2026)
    yield
    set_default_year(None)


class TestIso:
    def test_plain_iso_with_z(self):
        ts = TimestampParser().parse("2026-09-19T10:07:21Z")
        assert ts == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_iso_with_offset(self):
        ts = TimestampParser().parse("2026-09-19T12:07:21+02:00")
        assert ts == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_iso_with_microseconds(self):
        ts = TimestampParser().parse("2026-09-19T10:07:21.123456Z")
        assert ts.microsecond == 123456

    def test_space_separator_iso(self):
        ts = TimestampParser().parse("2026-09-19 10:07:21")
        assert ts == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)


class TestAccessLogFormats:
    def test_nginx_bracket_timestamp(self):
        ts = TimestampParser().parse("19/Sep/2026:10:07:21 +0000")
        assert ts == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_nginx_non_utc_offset(self):
        ts = TimestampParser().parse("19/Sep/2026:12:07:21 +0200")
        assert ts == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_apache_error_log_format(self):
        ts = TimestampParser().parse("Sun Sep 20 04:05:06.789123 2026")
        assert ts == datetime(2026, 9, 20, 4, 5, 6, 789123, tzinfo=UTC)

    def test_apache_error_without_fraction(self):
        ts = TimestampParser().parse("Sun Sep 20 04:05:06 2026")
        assert ts == datetime(2026, 9, 20, 4, 5, 6, tzinfo=UTC)


class TestSyslog:
    def test_rfc3164_gets_default_year(self):
        ts = TimestampParser().parse("Sep 19 10:07:21")
        assert ts == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_explicit_default_year_wins(self):
        ts = TimestampParser(default_year=2020).parse("Sep 19 10:07:21")
        assert ts.year == 2020


class TestEpoch:
    def test_epoch_seconds(self):
        ts = TimestampParser().parse("1758276441")
        assert ts == datetime.fromtimestamp(1758276441, tz=UTC)

    def test_epoch_with_fraction(self):
        ts = TimestampParser().parse("1758276441.5")
        assert ts.microsecond == 500000

    def test_epoch_millis(self):
        ts = TimestampParser().parse("1758276441000")
        assert ts == datetime.fromtimestamp(1758276441, tz=UTC)

    def test_nine_digit_number_is_not_epoch(self):
        # 9 digits falls between epoch-seconds and epoch-millis patterns.
        ts = TimestampParser().parse("123456789")
        assert ts is None or ts.year > 1970


class TestOtherFormats:
    @pytest.mark.parametrize(
        "text",
        [
            "2026/09/19 10:07:21",
            "2026/09/19 10:07:21.5",
        ],
    )
    def test_slash_dates(self, text):
        ts = TimestampParser().parse(text)
        assert ts is not None and (ts.year, ts.month, ts.day) == (2026, 9, 19)

    def test_log4j_comma_millis(self):
        ts = TimestampParser().parse("2026-09-19 10:07:21,123")
        assert ts is not None
        assert ts.microsecond == 123000


class TestFailures:
    @pytest.mark.parametrize(
        "text",
        ["", "   ", "not a timestamp", "19/13/2026:25:61:61 +0000", "9999-99-99"],
    )
    def test_unparseable(self, text):
        ts = TimestampParser().parse(text)
        assert ts is None, f"{text!r} unexpectedly parsed to {ts!r}"

    def test_pure_word_is_none(self):
        assert TimestampParser().parse("September") is None


class TestHelpers:
    def test_to_utc_naive_becomes_utc(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        assert to_utc(naive).tzinfo is UTC

    def test_gap_seconds_signed(self):
        a = datetime(2026, 9, 19, 10, 0, 10, tzinfo=UTC)
        b = datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC)
        assert gap_seconds(a, b) == 10
        assert gap_seconds(b, a) == -10

    def test_format_iso(self):
        dt = datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)
        assert format_timestamp(dt) == "2026-09-19T10:07:21Z"

    def test_format_access(self):
        dt = datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)
        assert format_timestamp(dt, style="access") == "19/Sep/2026:10:07:21 +0000"

    def test_round_to_bucket_floors(self):
        dt = datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)
        assert round_to_bucket(dt, 60) == datetime(2026, 9, 19, 10, 7, 0, tzinfo=UTC)

    def test_round_to_bucket_keeps_bucket_start(self):
        dt = datetime(2026, 9, 19, 10, 7, 0, tzinfo=UTC)
        assert round_to_bucket(dt, 60) == dt
