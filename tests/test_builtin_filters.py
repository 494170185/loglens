"""M15 — built-in predicates and record bridging."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from loglens.filters.builtin import (
    FromSource,
    HasField,
    HasTimestamp,
    LevelAtLeast,
    RegexFilter,
    apply_filter,
    expand_shorthand,
    matches_filter,
    record_context,
)
from loglens.model import Record


def rec(**kw):
    fields = kw.pop("fields", {})
    return Record(raw=kw.pop("raw", ""), message=kw.pop("message", ""), fields=fields, **kw)


class TestRecordContext:
    def test_fields_message_raw_level(self):
        r = rec(raw="R", message="M", level="error", fields={"status": 500})
        ctx = record_context(r)
        assert ctx["status"] == 500
        assert ctx["message"] == "M"
        assert ctx["raw"] == "R"
        assert ctx["level"] == "error"

    def test_field_overrides_builtin_keys(self):
        # explicit fields win over message/level builtins
        r = rec(fields={"level": "custom"})
        assert record_context(r)["level"] == "custom"

    def test_timestamp_included(self):
        ts = datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC)
        assert record_context(rec(timestamp=ts))["timestamp"] == ts


class TestLevelAtLeast:
    def test_threshold_error_matches_error_critical(self):
        p = LevelAtLeast("error")
        assert p(rec(level="error"))
        assert p(rec(level="critical"))
        assert not p(rec(level="warn"))
        assert not p(rec(level=None))

    def test_unknown_threshold_raises(self):
        with pytest.raises(ValueError):
            LevelAtLeast("banana")


class TestHasField:
    def test_present(self):
        assert HasField("status")(rec(fields={"status": 500}))

    def test_absent(self):
        assert not HasField("status")(rec(fields={}))

    def test_empty_string_is_absent(self):
        assert not HasField("user")(rec(fields={"user": ""}))

    def test_builtin_message(self):
        assert HasField("message")(rec(message="hi"))
        assert not HasField("message")(rec(message=""))


class TestHasTimestamp:
    def test_with_and_without(self):
        ts = datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC)
        assert HasTimestamp()(rec(timestamp=ts))
        assert not HasTimestamp()(rec())


class TestFromSource:
    def test_exact(self):
        assert FromSource("a.log")(rec(source="a.log"))

    def test_suffix_with_path(self):
        assert FromSource("a.log")(rec(source="/var/log/a.log"))
        assert FromSource("a.log")(rec(source=r"C:\logs\a.log"))

    def test_mismatch(self):
        assert not FromSource("b.log")(rec(source="a.log"))
        assert not FromSource("a.log")(rec(source=None))


class TestRegexFilter:
    def test_matches_message_or_raw(self):
        p = RegexFilter(r"timeout \d+")
        assert p(rec(message="timeout 5s"))
        assert p(rec(raw="timeout 30"))
        assert not p(rec(message="ok", raw="ok"))

    def test_invalid_pattern_raises_valueerror(self):
        with pytest.raises(ValueError):
            RegexFilter("[bad")


class TestApply:
    def test_apply_with_string(self):
        records = [
            rec(fields={"level": "error", "status": 500}),
            rec(fields={"level": "info", "status": 200}),
        ]
        out = apply_filter(records, "level = error")
        assert len(out) == 1

    def test_matches_filter_word(self):
        assert matches_filter(rec(message="timeout occurred"), "timeout")
        assert not matches_filter(rec(message="all good"), "timeout")

    def test_compiled_filter_reuse(self):
        from loglens.filters.parser import compile_filter

        f = compile_filter("status >= 500")
        records = [rec(fields={"status": 503}), rec(fields={"status": 200})]
        assert len(apply_filter(records, f)) == 1


class TestShorthands:
    def test_level_plus_expansion(self):
        assert expand_shorthand("level:warn+") == (
            "level = warning or level = error or level = critical"
        )

    def test_level_error_plus(self):
        assert expand_shorthand("level:error+") == "level = error or level = critical"

    def test_plain_level_no_plus(self):
        assert expand_shorthand("level:debug") == "level = debug"

    def test_unknown_level_untouched(self):
        assert expand_shorthand("level:banana") == "level:banana"

    def test_no_shorthand_untouched(self):
        assert expand_shorthand("status = 500") == "status = 500"

    def test_query_with_shorthand_matches(self):
        from loglens.filters.builtin import compile_query

        f = compile_query("level:error+")
        assert f.matches(record_context(rec(level="critical")))
        assert not f.matches(record_context(rec(level="info")))
