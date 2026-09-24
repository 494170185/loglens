"""M36 — CLI entry point tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from loglens.cli import build_parser, main, resolve_files

NGINX_LINES = [
    '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 512',
    '1.2.3.4 - - [19/Sep/2026:10:07:22 +0000] "GET /a HTTP/1.1" 404 90',
    '5.6.7.8 - - [19/Sep/2026:10:07:23 +0000] "POST /login HTTP/1.1" 500 10',
]


@pytest.fixture()
def access_log(tmp_path: Path):
    f = tmp_path / "access.log"
    f.write_text("\n".join(NGINX_LINES) + "\n", encoding="utf-8")
    return f


class TestParser:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "loglens" in out

    def test_command_required(self):
        with pytest.raises(SystemExit):
            main([])

    def test_all_subcommands_registered(self):
        parser = build_parser()
        # argparse exposes choices through the subparsers action
        actions = [a for a in parser._actions if a.dest == "command"]
        assert actions, "no subcommand action found"
        choices = actions[0].choices
        expected = {
            "cat", "stats", "filter", "grep", "top", "hist", "timeline",
            "report", "bursts", "anomalies", "silences", "sessions",
            "watch", "classify", "doctor",
        }
        missing = expected - set(choices)
        assert not missing, f"missing subcommands: {missing}"


class TestResolveFiles:
    def test_empty(self):
        assert resolve_files([]) == []

    def test_expansion(self, tmp_path: Path):
        f = tmp_path / "x.log"
        f.write_text("a", encoding="utf-8")
        assert resolve_files([str(f)]) == [str(f)]

    def test_glob(self, tmp_path: Path):
        (tmp_path / "a.log").write_text("a", encoding="utf-8")
        (tmp_path / "b.log").write_text("b", encoding="utf-8")
        assert len(resolve_files([str(tmp_path / "*.log")])) == 2


class TestCat:
    def test_cat_text(self, capsys, access_log):
        code = main(["cat", str(access_log)])
        out = capsys.readouterr().out
        assert code == 0
        assert "GET /" in out

    def test_cat_jsonl(self, capsys, access_log):
        main(["cat", str(access_log), "-f", "jsonl"])
        out = capsys.readouterr().out
        assert '"f_status": 200' in out

    def test_cat_limit(self, capsys, access_log):
        main(["cat", str(access_log), "-n", "1"])
        out = capsys.readouterr().out
        assert out.count("\n") == 1

    def test_cat_query_filter(self, capsys, access_log):
        main(["cat", str(access_log), "-q", "status >= 500"])
        out = capsys.readouterr().out
        assert "POST /login" in out
        assert "GET /" not in out

    def test_cat_csv(self, capsys, access_log):
        main(["cat", str(access_log), "-f", "csv"])
        out = capsys.readouterr().out
        assert out.startswith("timestamp,level,message")

    def test_cat_format_hint_raw(self, capsys, access_log):
        main(["cat", str(access_log), "--format-hint", "raw", "-f", "jsonl"])
        out = capsys.readouterr().out
        assert '"f_status"' not in out


class TestBadUsage:
    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            main(["definitely-not-a-command"])

    def test_cat_missing_query_value_exits(self):
        with pytest.raises(SystemExit):
            main(["cat", "-q"])

