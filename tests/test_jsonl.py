"""M6 — JSON Lines parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.parsers.jsonl import looks_like_json, parse_json_line, render_value


class TestBasicParsing:
    def test_flat_json_line(self):
        rec = parse_json_line('{"level": "error", "message": "boom"}')
        assert rec is not None
        assert rec.level == "error"
        assert rec.message == "boom"

    def test_timestamp_string_parsed(self):
        rec = parse_json_line('{"ts": "2026-09-19T10:07:21Z", "msg": "x"}')
        assert rec is not None
        assert rec.timestamp == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_level_alias_severity(self):
        rec = parse_json_line('{"severity": "WARN", "msg": "careful"}')
        assert rec is not None
        assert rec.level == "warning"

    def test_non_json_returns_none(self):
        assert parse_json_line("plain text") is None
        assert parse_json_line("[1,2,3]") is None
        assert parse_json_line('{"broken"') is None

    def test_json_array_is_not_a_record(self):
        assert parse_json_line('{"a": 1}') is not None
        assert parse_json_line('[{"a": 1}]') is None

    def test_source_and_line_no(self):
        rec = parse_json_line('{"a": 1}', source="app.jsonl", line_no=3)
        assert rec.source == "app.jsonl"
        assert rec.line_no == 3


class TestFlattening:
    def test_nested_object_flattened_with_underscore(self):
        rec = parse_json_line('{"http": {"status": 500}, "msg": "e"}')
        assert rec is not None
        assert rec.fields["http_status"] == 500

    def test_doubly_nested_keeps_two_levels(self):
        rec = parse_json_line('{"a": {"b": {"c": 1}}}')
        assert rec is not None
        assert "a_b" in rec.fields

    def test_at_prefix_stripped(self):
        rec = parse_json_line('{"@timestamp": "2026-09-19T10:07:21Z"}')
        assert rec is not None
        assert rec.timestamp == datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)

    def test_top_level_keys_win_over_nested(self):
        rec = parse_json_line('{"status": 1, "http": {"status": 500}}')
        assert rec is not None
        assert rec.fields["status"] == 1


class TestMessageFallback:
    def test_missing_message_becomes_empty(self):
        rec = parse_json_line('{"a": 1}')
        assert rec is not None
        assert rec.message == ""

    def test_event_key_used_as_message(self):
        rec = parse_json_line('{"event": "user_login"}')
        assert rec is not None
        assert rec.message == "user_login"


class TestHeuristic:
    def test_looks_like_json_true(self):
        assert looks_like_json('{"a": 1}')
        assert looks_like_json('  {"a": 1}  ')

    def test_looks_like_json_false(self):
        assert not looks_like_json("plain")
        assert not looks_like_json("{broken")
        assert not looks_like_json("")


class TestRenderValue:
    def test_none_renders_empty(self):
        assert render_value(None) == ""

    def test_bool_renders_lowercase(self):
        assert render_value(True) == "true"
        assert render_value(False) == "false"

    def test_integral_float_renders_without_dot(self):
        assert render_value(200.0) == "200"

    def test_fractional_float_kept(self):
        assert render_value(0.5) == "0.5"

    def test_list_renders_compact_json(self):
        assert render_value(["b", "a"]) == '["b","a"]'

    def test_string_passthrough(self):
        assert render_value("x") == "x"
