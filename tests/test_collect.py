"""M12 — the collection pipeline."""

from __future__ import annotations

from pathlib import Path

from loglens.collect import Collector

NGINX = "\n".join(
    [
        '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 512',
        '1.2.3.4 - - [19/Sep/2026:10:07:22 +0000] "GET /a HTTP/1.1" 404 90',
        '5.6.7.8 - - [19/Sep/2026:10:07:23 +0000] "POST /login HTTP/1.1" 500 10',
    ]
)

APPLOG = "\n".join(
    [
        "2026-09-19 10:07:21 INFO service starting",
        "2026-09-19 10:07:22 ERROR database query failed",
        "Traceback (most recent call last):",
        '  File "app.py", line 10, in run',
        "ValueError: connection refused",
        "2026-09-19 10:07:25 INFO retrying",
    ]
)


class TestCollectFile:
    def test_nginx_file_detected_and_parsed(self, tmp_path: Path):
        f = tmp_path / "access.log"
        f.write_text(NGINX, encoding="utf-8")
        records = Collector().collect_file(f)
        assert len(records) == 3
        assert records[0].fields["status"] == 200
        assert records[2].fields["status"] == 500

    def test_applog_stitches_traceback(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text(APPLOG, encoding="utf-8")
        records = Collector().collect_file(f)
        # 4 logical records: info, error+traceback, info
        assert len(records) == 3
        error_rec = records[1]
        assert error_rec.level == "error"
        assert "ValueError" in error_rec.raw
        assert error_rec.raw.count("\n") == 3

    def test_stitch_disabled(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text(APPLOG, encoding="utf-8")
        records = Collector(stitch=False).collect_file(f)
        assert len(records) == 6

    def test_explicit_format_overrides_detection(self, tmp_path: Path):
        f = tmp_path / "odd.log"
        f.write_text(NGINX, encoding="utf-8")
        records = Collector().collect_file(f, fmt="raw")
        # raw keeps no parsed status field, but enrichment still finds the ip
        assert "status" not in records[0].fields
        assert records[0].message.startswith("1.2.3.4")

    def test_source_and_line_numbers(self, tmp_path: Path):
        f = tmp_path / "access.log"
        f.write_text(NGINX, encoding="utf-8")
        records = Collector(stitch=False).collect_file(f)
        assert records[0].source is not None
        assert records[0].line_no == 1

    def test_stats_populated(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text(APPLOG, encoding="utf-8")
        collector = Collector()
        collector.collect_file(f)
        stats = collector.last_stats
        assert stats.lines_read == 6
        assert stats.records_emitted == 3
        assert stats.format == "plain"
        assert stats.continuations_folded == 3


class TestCollectLines:
    def test_in_memory_lines(self):
        records = Collector().collect_lines(
            ['{"msg": "hi", "level": "error"}', '{"msg": "there"}']
        )
        assert records[0].level == "error"
        assert records[0].message == "hi"

    def test_enrichment_applied(self):
        records = Collector().collect_lines(["2026-09-19 10:07:21 ERROR from 1.2.3.4"])
        assert records[0].fields.get("ip") == "1.2.3.4"

    def test_enrichment_disabled(self):
        records = Collector(enrich=False).collect_lines(
            ["2026-09-19 10:07:21 ERROR from 1.2.3.4"]
        )
        assert "ip" not in records[0].fields

    def test_empty_input(self):
        assert Collector().collect_lines([]) == []


class TestStreaming:
    def test_iter_file_is_lazy(self, tmp_path: Path):
        f = tmp_path / "access.log"
        f.write_text(NGINX, encoding="utf-8")
        it = Collector().iter_file(f)
        first = next(it)
        assert first.fields["status"] == 200
        rest = list(it)
        assert len(rest) == 2
