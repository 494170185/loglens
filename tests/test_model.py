"""M1 — the Record model that every parser produces."""

from __future__ import annotations

from datetime import datetime

from loglens.model import Record


class TestRecordBasics:
    def test_minimal_record_has_raw_and_message(self):
        rec = Record(raw="x", message="x")
        assert rec.raw == "x"
        assert rec.timestamp is None
        assert rec.level is None
        assert rec.fields == {}

    def test_get_reads_structured_fields_first(self):
        rec = Record(raw="x", message="msg body", fields={"message": "field wins"})
        assert rec.get("message") == "field wins"

    def test_get_falls_back_to_builtin_attributes(self):
        rec = Record(raw="x", message="body", level="warn")
        assert rec.get("level") == "warn"
        assert rec.get("message") == "body"

    def test_get_unknown_key_returns_default(self):
        rec = Record(raw="x")
        assert rec.get("nope") is None
        assert rec.get("nope", "?") == "?"

    def test_getitem_raises_keyerror_for_missing(self):
        import pytest

        rec = Record(raw="x")
        with pytest.raises(KeyError):
            _ = rec["nope"]

    def test_contains_covers_fields_and_builtins(self):
        rec = Record(raw="x", message="m", level="info", fields={"pid": 42})
        assert "pid" in rec
        assert "message" in rec
        assert "level" in rec
        assert "timestamp" in rec
        assert "absent" not in rec


class TestRecordCopies:
    def test_with_message_returns_new_record(self):
        rec = Record(raw="x", message="old")
        new = rec.with_message("new")
        assert new.message == "new"
        assert rec.message == "old"
        assert new.raw == "x"

    def test_merged_copies_fields_without_mutation(self):
        rec = Record(raw="x", fields={"a": 1, "b": 2})
        out = rec.merged({"b": 3, "c": 4})
        assert out.fields == {"a": 1, "b": 3, "c": 4}
        assert rec.fields == {"a": 1, "b": 2}

    def test_timestamp_and_source_survive_copies(self):
        ts = datetime(2026, 9, 19, 10, 0, 0)
        rec = Record(raw="x", timestamp=ts, source="a.log", line_no=7)
        out = rec.with_message("m").merged({"k": 1})
        assert out.timestamp == ts
        assert out.source == "a.log"
        assert out.line_no == 7
