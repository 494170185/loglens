"""M7 — logfmt parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.parsers.logfmt import looks_like_logfmt, parse_logfmt_line


class TestBasics:
    def test_simple_pairs(self):
        rec = parse_logfmt_line("level=info msg=starting port=8080")
        assert rec is not None
        assert rec.fields["level"] == "info"
        assert rec.fields["msg"] == "starting"
        assert rec.fields["port"] == 8080
        assert rec.level == "info"
        assert rec.message == "starting"

    def test_quoted_values_with_spaces(self):
        rec = parse_logfmt_line('msg="hello world" status=200')
        assert rec is not None
        assert rec.fields["msg"] == "hello world"

    def test_escaped_quote_inside_value(self):
        rec = parse_logfmt_line(r'msg="say \"hi\""')
        assert rec is not None
        assert rec.fields["msg"] == 'say "hi"'

    def test_single_quoted_value(self):
        rec = parse_logfmt_line("msg='single quoted'")
        assert rec is not None
        assert rec.fields["msg"] == "single quoted"

    def test_no_pairs_returns_none(self):
        assert parse_logfmt_line("just words here") is None
        assert parse_logfmt_line("") is None

    def test_pair_without_value_still_needs_equals(self):
        # "key=" with nothing after is still a valid empty pair
        rec = parse_logfmt_line("key= next=1")
        assert rec is not None
        assert rec.fields["key"] == ""
        assert rec.fields["next"] == 1


class TestCoercion:
    def test_int_coercion(self):
        rec = parse_logfmt_line("dur=42 status=200")
        assert rec is not None
        assert rec.fields["dur"] == 42
        assert rec.fields["status"] == 200

    def test_float_coercion(self):
        rec = parse_logfmt_line("latency=0.125")
        assert rec is not None
        assert rec.fields["latency"] == 0.125

    def test_bool_coercion(self):
        rec = parse_logfmt_line("ok=true failed=false")
        assert rec is not None
        assert rec.fields["ok"] is True
        assert rec.fields["failed"] is False

    def test_null_and_dash_coercion(self):
        rec = parse_logfmt_line("user=null ref=-")
        assert rec is not None
        assert rec.fields["user"] is None
        assert rec.fields["ref"] == ""

    def test_version_string_not_coerced(self):
        rec = parse_logfmt_line("version=1.2.3")
        assert rec is not None
        assert rec.fields["version"] == "1.2.3"


class TimestampsAndLevels:
    def test_time_key_parsed(self):
        rec = parse_logfmt_line("time=2026-09-19T10:07:21Z msg=x")
        assert rec is not None
        assert rec.timestamp == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_ts_alias(self):
        rec = parse_logfmt_line("ts=2026-09-19T10:07:21Z")
        assert rec is not None
        assert rec.timestamp is not None

    def test_unknown_level_falls_back_none(self):
        rec = parse_logfmt_line("level=banana msg=x")
        assert rec is not None
        assert rec.level is None


class TestHeuristic:
    def test_two_pairs_recognized(self):
        assert looks_like_logfmt("a=1 b=2")

    def test_plain_text_not_logfmt(self):
        assert not looks_like_logfmt("no equals signs")
        assert not looks_like_logfmt("")
