"""M23/M24 — gzip sources and merged multi-file input."""

from __future__ import annotations

import gzip as gzip_mod
from datetime import UTC, datetime
from pathlib import Path

from loglens.model import Record
from loglens.sources import (
    MergedSource,
    gunzip_bytes,
    gzip_bytes,
    is_gzip,
    merge_files,
    normalize_paths,
    read_lines_any,
)


class TestGzipReading:
    def test_gzip_file_read_transparently(self, tmp_path: Path):
        f = tmp_path / "app.log.gz"
        f.write_bytes(gzip_bytes(b"one\ntwo\n"))
        assert list(read_lines_any(f)) == [(1, "one"), (2, "two")]

    def test_plain_file_still_works(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_bytes(b"one\ntwo\n")
        assert list(read_lines_any(f)) == [(1, "one"), (2, "two")]

    def test_renamed_gzip_detected_by_magic(self, tmp_path: Path):
        f = tmp_path / "oddname.dat"
        f.write_bytes(gzip_bytes(b"x\n"))
        assert list(read_lines_any(f)) == [(1, "x")]

    def test_is_gzip(self, tmp_path: Path):
        plain = tmp_path / "a.log"
        plain.write_bytes(b"hi")
        zipped = tmp_path / "b.gz"
        zipped.write_bytes(gzip_bytes(b"hi"))
        assert not is_gzip(plain)
        assert is_gzip(zipped)

    def test_stdlib_gzip_module_compatible(self, tmp_path: Path):
        f = tmp_path / "c.gz"
        with open(f, "wb") as handle, gzip_mod.GzipFile(fileobj=handle, mode="wb") as gz:
            gz.write(b"a\nb\n")
        assert list(read_lines_any(f)) == [(1, "a"), (2, "b")]


class TestGunzipHelpers:
    def test_roundtrip(self):
        data = b"payload"
        assert gunzip_bytes(gzip_bytes(data)) == data

    def test_passthrough_non_gzip(self):
        assert gunzip_bytes(b"plain") == b"plain"


def rec(ts, **kw):
    stamp = (
        ts
        if isinstance(ts, datetime)
        else datetime(2026, 9, 19, 10, ts, 0, tzinfo=UTC)
    )
    return Record(raw="", message="", timestamp=stamp, **kw)


class TestMergedSource:
    def test_interleaves_by_timestamp(self):
        early = [rec(5, source="a.log")]
        late = [rec(1, source="b.log"), rec(9, source="b.log")]
        merged = MergedSource().merge([early, late])
        assert [r.source for r in merged] == ["b.log", "a.log", "b.log"]

    def test_tie_keeps_arrival_order(self):
        one = [rec(5, source="a.log")]
        two = [rec(5, source="b.log")]
        merged = MergedSource().merge([one, two])
        assert [r.source for r in merged] == ["a.log", "b.log"]

    def test_no_timestamp_records_sort_last(self):
        stamped = [rec(1)]
        unstamped = [Record(raw="", message="", source="c.log")]
        merged = MergedSource().merge([unstamped, stamped])
        assert merged[0].timestamp is not None
        assert merged[1].timestamp is None

    def test_empty_streams(self):
        assert MergedSource().merge([[], []]) == []


class TestMergeFiles:
    def test_merge_two_files(self, tmp_path: Path):
        a = tmp_path / "a.log"
        a.write_text("2026-09-19 10:05:00 INFO late\n", encoding="utf-8")
        b = tmp_path / "b.log"
        b.write_text("2026-09-19 10:01:00 INFO early\n", encoding="utf-8")
        from loglens.collect import Collector

        records = merge_files([a, b], Collector().collect_file)
        assert records[0].fields == {} or records[0].message == "early"
        assert records[0].timestamp is not None
        assert records[0].timestamp < records[1].timestamp


class TestNormalizePaths:
    def test_directory_expansion(self, tmp_path: Path):
        (tmp_path / "one.log").write_text("a\n", encoding="utf-8")
        (tmp_path / "two.log.gz").write_bytes(gzip_bytes(b"b\n"))
        (tmp_path / "ignore.txt.bak").write_text("x", encoding="utf-8")
        paths = normalize_paths([str(tmp_path)])
        names = [p.name for p in paths]
        assert "one.log" in names
        assert "two.log.gz" in names
        assert len(names) == 2

    def test_glob_pattern(self, tmp_path: Path):
        (tmp_path / "x1.log").write_text("a", encoding="utf-8")
        (tmp_path / "x2.log").write_text("b", encoding="utf-8")
        paths = normalize_paths([str(tmp_path / "x*.log")])
        assert len(paths) == 2

    def test_dedup(self, tmp_path: Path):
        f = tmp_path / "a.log"
        f.write_text("a", encoding="utf-8")
        paths = normalize_paths([str(f), str(f)])
        assert len(paths) == 1

    def test_missing_file_dropped(self):
        assert normalize_paths(["definitely-not-here.log"]) == []

    def test_plain_file_kept(self, tmp_path: Path):
        f = tmp_path / "single.log"
        f.write_text("a", encoding="utf-8")
        assert normalize_paths([str(f)]) == [f]
