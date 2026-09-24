"""M42d — tests for formatcheck and offsets."""

from __future__ import annotations

from pathlib import Path

from loglens.formatcheck import (
    audit_format,
    consistency_issues,
    per_line_format,
)
from loglens.model import Record
from loglens.offsets import OffsetState, OffsetStore, unseen_bytes


def rec(raw="", msg="", **kw):
    return Record(raw=raw, message=msg, **kw)


class TestPerLineFormat:
    def test_json(self):
        assert per_line_format('{"a": 1}') == "json"

    def test_access(self):
        line = '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10'
        assert per_line_format(line) == "access"

    def test_syslog(self):
        assert per_line_format("Sep 19 10:07:21 host app: m") == "syslog"

    def test_plain(self):
        assert per_line_format("2026-09-19 10:07:21 INFO x") == "plain"

    def test_raw(self):
        assert per_line_format("anything else") == "raw"


class TestAudit:
    def test_counts(self):
        records = [
            rec(raw="2026-09-19 10:00:00 INFO a", msg="a", level="info"),
            rec(raw="plain b", msg="b"),
        ]
        report = audit_format(records)
        assert report.total == 2
        assert report.with_level == 1
        assert report.timestamp_coverage == 0.0

    def test_empty(self):
        report = audit_format([])
        assert report.dominant_format == "raw"

    def test_dominant(self):
        records = [rec(raw='{"a": 1}')] * 5 + [rec(raw="noise")]
        assert audit_format(records).dominant_format == "json"


class TestConsistencyIssues:
    def test_empty_stream_reported(self):
        report = audit_format([])
        issues = consistency_issues(report)
        assert issues[0].kind == "empty"

    def test_clean_stream(self):
        records = [
            rec(raw="2026-09-19 10:00:00 INFO a", msg="a", level="info", timestamp=None)
        ]
        # plain format, but missing timestamps and levels raise issues
        issues = consistency_issues(audit_format(records))
        kinds = {i.kind for i in issues}
        assert "missing-timestamps" in kinds

    def test_access_logs_skip_level_check(self):
        line = '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10'
        records = [rec(raw=line, msg="m")]
        issues = consistency_issues(audit_format(records))
        kinds = {i.kind for i in issues}
        assert "missing-levels" not in kinds


class TestOffsetStore:
    def test_roundtrip(self, tmp_path: Path):
        store = OffsetStore(tmp_path / "state.json")
        states = {"a.log": OffsetState(path="a.log", offset=100, line_no=5, size=100)}
        store.save(states)
        loaded = store.load()
        assert loaded["a.log"].offset == 100
        assert loaded["a.log"].line_no == 5

    def test_missing_file_empty(self, tmp_path: Path):
        assert OffsetStore(tmp_path / "nope.json").load() == {}

    def test_corrupt_file_empty(self, tmp_path: Path):
        f = tmp_path / "state.json"
        f.write_text("{broken", encoding="utf-8")
        assert OffsetStore(f).load() == {}

    def test_version_mismatch_empty(self, tmp_path: Path):
        f = tmp_path / "state.json"
        f.write_text('{"version": 99, "files": []}', encoding="utf-8")
        assert OffsetStore(f).load() == {}

    def test_record(self, tmp_path: Path):
        f = tmp_path / "x.log"
        f.write_bytes(b"0123456789")
        state = OffsetStore(tmp_path / "s.json").record(f)
        assert state.offset == 10

    def test_is_fresh(self, tmp_path: Path):
        f = tmp_path / "x.log"
        f.write_bytes(b"0123456789")
        store = OffsetStore(tmp_path / "s.json")
        state = store.record(f)
        assert store.is_fresh(state, f)
        f.write_bytes(b"0123456789ABC")
        assert not store.is_fresh(state, f)

    def test_unseen_bytes(self, tmp_path: Path):
        f = tmp_path / "x.log"
        f.write_bytes(b"0123456789")
        state = OffsetState(path=str(f), offset=4, line_no=0, size=10)
        assert unseen_bytes(state, f) == 6
