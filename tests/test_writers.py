"""M32/M33 — writers and ANSI colors."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loglens.ansi import (
    colors_enabled,
    level_style,
    paint,
    paint_level,
    strip_ansi,
)
from loglens.model import Record
from loglens.writers import (
    read_jsonl,
    record_to_dict,
    write_csv,
    write_json,
    write_jsonl,
    write_records,
    write_text,
)


def sample_records():
    ts = datetime(2026, 9, 19, 10, 7, 21, tzinfo=UTC)
    first = Record(
        raw="raw one", message="one", timestamp=ts, level="error",
        source="a.log", line_no=1, fields={"status": 500},
    )
    second = Record(raw="raw two", message="two", level="info")
    return [first, second]


class TestRecordToDict:
    def test_flat_mapping(self):
        d = record_to_dict(sample_records()[0])
        assert d["raw"] == "raw one"
        assert d["message"] == "one"
        assert d["level"] == "error"
        assert d["source"] == "a.log"
        assert d["line_no"] == 1
        assert d["f_status"] == 500
        assert d["timestamp"].startswith("2026-09-19T10:07:21")

    def test_optional_fields_omitted(self):
        d = record_to_dict(sample_records()[1])
        assert "timestamp" not in d
        assert "source" not in d
        assert "line_no" not in d


class TestText:
    def test_raw_lines_joined(self):
        assert write_text(sample_records()) == "raw one\nraw two"


class TestJson:
    def test_jsonl_roundtrip(self):
        text = write_jsonl(sample_records())
        lines = read_jsonl(text)
        assert lines[0]["message"] == "one"
        assert lines[1]["level"] == "info"

    def test_json_array(self):
        text = write_json(sample_records())
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["f_status"] == 500

    def test_jsonl_no_trailing_newline(self):
        text = write_jsonl([sample_records()[0]])
        assert not text.endswith("\n")


class TestCsv:
    def test_default_columns(self):
        text = write_csv(sample_records())
        lines = text.strip().split("\n")
        assert lines[0] == "timestamp,level,message,source,line_no"
        assert "error" in lines[1]

    def test_field_columns(self):
        text = write_csv(sample_records(), columns=["level", "f_status"])
        lines = text.strip().split("\n")
        assert lines[0] == "level,f_status"
        assert lines[1] == "error,500"
        assert lines[2] == "info,"

    def test_bool_rendering(self):
        rec = Record(raw="", message="", fields={"ok": True})
        text = write_csv([rec], columns=["f_ok"])
        assert text.strip().split("\n")[1] == "true"


class TestWriteRecords:
    @pytest.mark.parametrize("fmt", ["text", "json", "jsonl", "csv"])
    def test_formats_render(self, fmt):
        text = write_records(sample_records(), fmt)
        assert text

    def test_unknown_format(self):
        with pytest.raises(ValueError):
            write_records([], "xml")

    def test_saves_to_file(self, tmp_path: Path):
        out = tmp_path / "out.jsonl"
        write_records(sample_records(), "jsonl", path=out)
        assert out.read_text(encoding="utf-8").startswith("{")


class TestColorsEnabled:
    def test_no_color_env_disables(self):
        assert not colors_enabled(stream_is_tty=True, env={"NO_COLOR": "1"})

    def test_force_color_overrides(self):
        assert colors_enabled(stream_is_tty=False, env={"FORCE_COLOR": "1"})

    def test_dumb_term_disables(self):
        assert not colors_enabled(stream_is_tty=True, env={"TERM": "dumb"})

    def test_plain_non_tty(self):
        assert not colors_enabled(stream_is_tty=False, env={})

    def test_tty_enabled(self):
        assert colors_enabled(stream_is_tty=True, env={})


class TestPaint:
    def test_paint_wraps(self):
        out = paint("hi", "red")
        assert out == "\x1b[31mhi\x1b[0m"

    def test_multiple_styles(self):
        out = paint("hi", "bold", "red")
        assert out.startswith("\x1b[1m\x1b[31m")

    def test_disabled_passthrough(self):
        assert paint("hi", "red", enabled=False) == "hi"

    def test_unknown_style_ignored(self):
        assert paint("hi", "sparkles") == "hi"

    def test_empty_text(self):
        assert paint("", "red") == ""

    def test_strip_ansi(self):
        assert strip_ansi("\x1b[31mhi\x1b[0m") == "hi"


class TestLevelColors:
    def test_level_style_mapping(self):
        assert level_style("error") == "red"
        assert level_style("warning") == "yellow"
        assert level_style("info") == "cyan"
        assert level_style("debug") == "dim"
        assert level_style(None) == "green"

    def test_paint_level(self):
        out = paint_level("error")
        assert "ERROR" in out
        assert "\x1b[31m" in out

    def test_paint_level_none(self):
        assert paint_level(None) == ""

    def test_paint_level_disabled(self):
        assert paint_level("error", enabled=False) == "ERROR"
