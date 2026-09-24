"""M37/M38 — remaining CLI subcommands."""

from __future__ import annotations

from pathlib import Path

import pytest

from loglens.cli import main

NGINX = "\n".join(
    [
        '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET /api/x HTTP/1.1" 200 512',
        '1.2.3.4 - - [19/Sep/2026:10:07:22 +0000] "GET /api/y HTTP/1.1" 404 90',
        '1.2.3.4 - - [19/Sep/2026:10:07:23 +0000] "POST /login HTTP/1.1" 500 10',
        '5.6.7.8 - - [19/Sep/2026:10:07:24 +0000] "GET /static/a.css HTTP/1.1" 200 90',
        '5.6.7.8 - - [19/Sep/2026:10:08:24 +0000] "GET /health HTTP/1.1" 200 5',
        '5.6.7.8 - - [19/Sep/2026:10:30:00 +0000] "GET /health HTTP/1.1" 200 5',
    ]
)


@pytest.fixture()
def access_log(tmp_path: Path):
    f = tmp_path / "access.log"
    f.write_text(NGINX + "\n", encoding="utf-8")
    return f


def run(capsys, *argv):
    code = main(list(argv))
    return code, capsys.readouterr().out


class TestStats:
    def test_overview(self, capsys, access_log):
        code, out = run(capsys, "stats", str(access_log))
        assert code == 0
        assert "records" in out
        assert "status errors" in out

    def test_with_query(self, capsys, access_log):
        code, out = run(capsys, "stats", str(access_log), "-q", "status >= 500")
        assert code == 0
        assert "records" in out


class TestFilter:
    def test_matches_only(self, capsys, access_log):
        code, out = run(capsys, "filter", str(access_log), "-q", "status = 404")
        assert code == 0
        assert "GET /api/y" in out
        assert "/login" not in out


class TestGrep:
    def test_substring(self, capsys, access_log):
        code, out = run(capsys, "grep", str(access_log), "login")
        assert code == 0
        assert out.count("\n") == 1

    def test_ignore_case(self, capsys, access_log):
        code, _out = run(capsys, "grep", str(access_log), "POST", "-i")
        assert code == 0

    def test_invert(self, capsys, access_log):
        code, out = run(capsys, "grep", str(access_log), "health", "-v")
        assert code == 0
        assert "health" not in out


class TestTop:
    def test_top_clients(self, capsys, access_log):
        code, out = run(capsys, "top", str(access_log), "client")
        assert code == 0
        assert "1.2.3.4" in out and "5.6.7.8" in out


class TestHist:
    def test_hist_runs(self, capsys, access_log):
        code, out = run(capsys, "hist", str(access_log), "bytes")
        assert code == 0
        assert "|" in out

    def test_hist_empty(self, capsys, access_log):
        code, out = run(capsys, "hist", str(access_log), "nonexistent")
        assert code == 0
        assert "no values" in out


class TestTimeline:
    def test_counts(self, capsys, access_log):
        code, out = run(capsys, "timeline", str(access_log))
        assert code == 0
        assert "events" in out
        assert "10:07" in out

    def test_error_series(self, capsys, access_log):
        code, out = run(capsys, "timeline", str(access_log), "--errors")
        assert code == 0
        assert "5xx" in out


class TestReport:
    def test_stdout(self, capsys, access_log):
        code, out = run(capsys, "report", str(access_log))
        assert code == 0
        assert "# loglens report" in out

    def test_output_file(self, capsys, access_log, tmp_path: Path):
        target = tmp_path / "r.md"
        code, out = run(capsys, "report", str(access_log), "-o", str(target))
        assert code == 0
        assert "written" in out
        assert target.read_text(encoding="utf-8").startswith("# loglens")


class TestBursts:
    def test_no_bursts(self, capsys, access_log):
        code, _out = run(capsys, "bursts", str(access_log))
        assert code == 0

    def test_burst_found(self, capsys, tmp_path: Path):
        f = tmp_path / "b.log"
        body = "\n".join(["timeout waiting for db"] * 6)
        f.write_text(body + "\n", encoding="utf-8")
        code, out = run(capsys, "bursts", str(f))
        assert code == 0
        assert "timeout waiting for db" in out


class TestAnomalies:
    def test_outlier_listed(self, capsys, tmp_path: Path):
        f = tmp_path / "d.log"
        lines = [f"2026-09-19 10:0{i}:00 INFO dur={v}ms" for i, v in enumerate([10] * 30 + [9000])]
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # the text extractor normalizes 'dur=10ms' into duration_ms
        code, out = run(capsys, "anomalies", str(f), "duration_ms")
        assert code == 0
        assert "9000" in out


class TestSilences:
    def test_gap_listed(self, capsys, access_log):
        code, out = run(capsys, "silences", str(access_log), "--min-seconds", "600")
        assert code == 0
        assert "10:08" in out
        assert "22m" in out


class TestSessions:
    def test_sessions_listed(self, capsys, access_log):
        code, out = run(capsys, "sessions", str(access_log))
        assert code == 0
        assert "1.2.3.4" in out


class TestClassify:
    def test_categories(self, capsys, access_log):
        code, out = run(capsys, "classify", str(access_log))
        assert code == 0
        assert "api" in out
        assert "health" in out
