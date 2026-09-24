"""M2 — readers: encoding fallback, newline handling, numbering."""

from __future__ import annotations

from pathlib import Path

import pytest

from loglens.readers import iter_lines_from, read_lines


class TestReadLines:
    def test_utf8_file_yields_stripped_lines(self, tmp_path: Path):
        f = tmp_path / "a.log"
        f.write_text("one\ntwo\n", encoding="utf-8")
        assert list(read_lines(f)) == [(1, "one"), (2, "two")]

    def test_crlf_line_endings_are_handled(self, tmp_path: Path):
        f = tmp_path / "win.log"
        f.write_bytes(b"a\r\nb\r\nc")
        assert list(read_lines(f)) == [(1, "a"), (2, "b"), (3, "c")]

    def test_latin1_fallback_keeps_bytes(self, tmp_path: Path):
        f = tmp_path / "raw.log"
        f.write_bytes("caf\xe9 open\n".encode("latin-1"))
        lines = list(read_lines(f))
        assert lines == [(1, "caf\xe9 open")]

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            list(read_lines(tmp_path / "nope.log"))

    def test_empty_file_yields_nothing(self, tmp_path: Path):
        f = tmp_path / "empty.log"
        f.write_text("", encoding="utf-8")
        assert list(read_lines(f)) == []


class TestIterLinesFrom:
    def test_splits_and_numbers(self):
        assert iter_lines_from("a\nb\nc\n") == [(1, "a"), (2, "b"), (3, "c")]

    def test_trailing_newline_without_final_eol(self):
        assert iter_lines_from("x\ny") == [(1, "x"), (2, "y")]

    def test_empty_string(self):
        assert iter_lines_from("") == []

    def test_strips_solo_carriage_returns(self):
        assert iter_lines_from("x\r\ny") == [(1, "x"), (2, "y")]
