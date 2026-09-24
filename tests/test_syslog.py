"""M8 — syslog RFC 3164 / 5424 parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.parsers.syslog import (
    facility_name,
    looks_like_syslog,
    parse_syslog_line,
)


class TestRfc3164:
    def test_basic_bsd_line(self):
        rec = parse_syslog_line("Sep 19 10:07:21 myhost sshd[1234]: Accepted password for root")
        assert rec is not None
        assert rec.timestamp == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)
        assert rec.fields["host"] == "myhost"
        assert rec.fields["tag"] == "sshd"
        assert rec.fields["pid"] == 1234
        assert rec.message == "Accepted password for root"

    def test_tag_without_pid(self):
        rec = parse_syslog_line("Sep 19 10:07:21 myhost cron: job started")
        assert rec is not None
        assert rec.fields["tag"] == "cron"
        assert "pid" not in rec.fields

    def test_single_digit_day(self):
        rec = parse_syslog_line("Sep  1 10:07:21 myhost app: x")
        assert rec is not None
        assert rec.timestamp.day == 1

    def test_custom_default_year(self):
        rec = parse_syslog_line("Sep 19 10:07:21 myhost app: x", default_year=2021)
        assert rec is not None
        assert rec.timestamp.year == 2021

    def test_bad_month_rejected(self):
        assert parse_syslog_line("Xyz 19 10:07:21 myhost app: x") is None


class TestRfc5424:
    def test_full_5424_line(self):
        line = "<34>1 2026-09-19T10:07:21.123Z myhost app 8710 ID47 - disk full"
        rec = parse_syslog_line(line)
        assert rec is not None
        assert rec.timestamp is not None
        assert rec.timestamp.microsecond == 123000
        assert rec.level == "critical"  # pri 34 = facility 4, severity 2
        assert rec.fields["host"] == "myhost"
        assert rec.fields["app"] == "app"
        assert rec.fields["pid"] == 8710
        assert rec.message == "disk full"

    def test_severity_info(self):
        line = "<14>1 2026-09-19T10:07:21Z h a 1 - - hello"
        rec = parse_syslog_line(line)
        assert rec is not None
        assert rec.level == "info"

    def test_structured_data_kept(self):
        line = '<30>1 2026-09-19T10:07:21Z h a 1 - [example sd] msg'
        rec = parse_syslog_line(line)
        assert rec is not None
        assert "example" in rec.fields["structured_data"]

    def test_non_digit_pid_not_coerced(self):
        line = "<30>1 2026-09-19T10:07:21Z h a web-1 - - m"
        rec = parse_syslog_line(line)
        assert rec is not None
        assert "pid" not in rec.fields


class TestHeuristic:
    def test_bsd_shape(self):
        assert looks_like_syslog("Sep 19 10:07:21 myhost app: x")
        assert not looks_like_syslog("not syslog at all")

    def test_5424_shape(self):
        assert looks_like_syslog("<34>1 2026-09-19T10:07:21Z h a 1 - - m")
        assert not looks_like_syslog("<34>1 broken")


class TestFacilityNames:
    def test_common_codes(self):
        assert facility_name(0) == "kernel"
        assert facility_name(3) == "daemon"
        assert facility_name(16) == "local0"
        assert facility_name(23) == "local7"

    def test_unknown_code(self):
        assert facility_name(99) == "facility99"
