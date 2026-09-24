"""M9 — format detection and plain-text parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.parsers.detect import FormatDetector, parse_plain_line, parse_with


class TestPlainParser:
    def test_timestamp_level_message(self):
        rec = parse_plain_line("2026-09-19 10:07:21 INFO service started")
        assert rec is not None
        assert rec.timestamp == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)
        assert rec.level == "info"
        assert rec.message == "service started"

    def test_iso_with_t(self):
        rec = parse_plain_line("2026-09-19T10:07:21Z ERROR boom")
        assert rec is not None
        assert rec.level == "error"

    def test_bracketed_level(self):
        rec = parse_plain_line("2026-09-19 10:07:21 [WARN] careful")
        assert rec is not None
        assert rec.level == "warning"
        assert rec.message == "careful"

    def test_bracketed_logger_kept_as_field(self):
        rec = parse_plain_line("2026-09-19 10:07:21 [auth.module] login failed")
        assert rec is not None
        assert rec.level is None
        assert rec.fields["logger"] == "auth.module"
        assert rec.message == "login failed"

    def test_no_timestamp_returns_none(self):
        assert parse_plain_line("just a message") is None

    def test_garbage_timestamp_returns_none(self):
        assert parse_plain_line("9999-99-99 99:99:99 INFO x") is None


class TestDetector:
    def test_detects_json(self):
        lines = ['{"a": 1}', '{"b": 2}', '{"c": 3}']
        assert FormatDetector().detect(lines) == "json"

    def test_detects_access(self):
        lines = [
            '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10'
            for _ in range(3)
        ]
        assert FormatDetector().detect(lines) == "access"

    def test_detects_syslog(self):
        lines = ["Sep 19 10:07:21 myhost app: msg"] * 3
        assert FormatDetector().detect(lines) == "syslog"

    def test_detects_logfmt(self):
        lines = ["level=info msg=one", "level=error msg=two", "level=info msg=three"]
        assert FormatDetector().detect(lines) == "logfmt"

    def test_detects_plain(self):
        lines = [
            "2026-09-19 10:07:21 INFO one",
            "2026-09-19 10:07:22 INFO two",
            "2026-09-19 10:07:23 WARN three",
        ]
        assert FormatDetector().detect(lines) == "plain"

    def test_unmatchable_becomes_raw(self):
        assert FormatDetector().detect(["lorem ipsum", "dolor sit"]) == "raw"

    def test_mixed_minority_does_not_win(self):
        # 3 json + 1 plain → json
        lines = ['{"a": 1}', '{"b": 2}', '{"c": 3}', "2026-09-19 10:07:21 INFO x"]
        assert FormatDetector().detect(lines) == "json"

    def test_detection_is_cached(self):
        det = FormatDetector()
        first = det.detect(["a=1 b=2"])
        assert det.format == "logfmt"
        second = det.detect(['{"x": 1}'])
        assert second == first == "logfmt"

    def test_window_limits_sample(self):
        det = FormatDetector(window=2)
        lines = ["plain text"] * 10 + ['{"a": 1}'] * 30
        assert det.detect(lines) == "raw"


class TestParseWith:
    def test_routes_json(self):
        rec = parse_with("json", '{"msg": "hi"}')
        assert rec.message == "hi"

    def test_routes_access(self):
        line = '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10'
        rec = parse_with("access", line)
        assert rec.fields["status"] == 200

    def test_routes_syslog(self):
        rec = parse_with("syslog", "Sep 19 10:07:21 myhost app: x")
        assert rec.fields["host"] == "myhost"

    def test_routes_logfmt(self):
        rec = parse_with("logfmt", "a=1")
        assert rec.fields["a"] == 1

    def test_routes_plain(self):
        rec = parse_with("plain", "2026-09-19 10:07:21 INFO x")
        assert rec.level == "info"

    def test_raw_never_fails(self):
        rec = parse_with("raw", "anything at all")
        assert rec.message == "anything at all"

    def test_failed_parse_falls_back_to_raw(self):
        # JSON parser returns None for non-JSON; must not crash.
        rec = parse_with("json", "not json")
        assert rec.message == "not json"

    def test_unknown_format_name_falls_back(self):
        rec = parse_with("does-not-exist", "hello")
        assert rec.message == "hello"
