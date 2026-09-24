"""M34 — terminal tables."""

from __future__ import annotations

from loglens.tables import display_width, pad_to, render_key_value, render_table, truncate


class TestDisplayWidth:
    def test_ascii_is_one(self):
        assert display_width("abc") == 3

    def test_cjk_is_two(self):
        assert display_width("中文") == 4

    def test_mixed(self):
        assert display_width("a中b") == 4

    def test_emoji_fallback(self):
        # unknown characters fall back to width 1 unless wide
        assert display_width("\U0001f600") >= 1

    def test_combining_marks_zero(self):
        assert display_width("e\u0301") == 1

    def test_empty(self):
        assert display_width("") == 0


class TestPad:
    def test_left_pad(self):
        assert pad_to("ab", 5) == "ab   "

    def test_right_pad(self):
        assert pad_to("ab", 5, align="right") == "   ab"

    def test_center_pad(self):
        assert pad_to("ab", 6, align="center") == "  ab  "

    def test_no_pad_when_long_enough(self):
        assert pad_to("abcdef", 4) == "abcdef"

    def test_cjk_pad_counts_display(self):
        assert pad_to("中", 4) == "中  "


class TestTruncate:
    def test_short_passthrough(self):
        assert truncate("abc", 10) == "abc"

    def test_truncated_with_ellipsis(self):
        out = truncate("abcdefgh", 5)
        assert display_width(out) == 5
        assert out.endswith("\u2026")

    def test_cjk_truncate(self):
        out = truncate("中文字符", 5)
        assert display_width(out) <= 5


class TestRenderTable:
    def test_basic_table_with_header(self):
        rows = [("a", "1"), ("bb", "22")]
        text = render_table(rows, headers=("name", "value"))
        lines = text.split("\n")
        assert lines[0] == "name | value"
        assert lines[1] == "----+-----" or lines[1] == "-----+------"
        assert lines[2].startswith("a    | 1")
        assert lines[3].startswith("bb   | 22")

    def test_no_header_no_rule(self):
        rows = [("x", "1")]
        text = render_table(rows)
        assert "-+-" not in text

    def test_right_alignment(self):
        rows = [("1", "x"), ("200", "y")]
        text = render_table(rows, aligns=("right", "left"))
        lines = text.split("\n")
        assert lines[0].startswith("  1 |")
        assert lines[1].startswith("200 |")

    def test_ragged_rows_padded(self):
        rows = [("a", "b"), ("c",)]
        text = render_table(rows, headers=("h1", "h2"))
        assert text.count("\n") == 3

    def test_empty_table(self):
        assert render_table([]) == ""

    def test_cjk_alignment(self):
        rows = [("中文", "1"), ("abc", "22")]
        text = render_table(rows, headers=("k", "v"))
        lines = text.split("\n")
        # pipe must sit at the same display column in every body row
        body_lines = [ln for ln in lines if "+" not in ln and "|" in ln]
        pipe_columns = {
            display_width(ln[: ln.index("|")]) for ln in body_lines
        }
        assert len(pipe_columns) == 1


class TestKeyValue:
    def test_aligned_block(self):
        text = render_key_value([("errors", "3"), ("total", "100")])
        lines = text.split("\n")
        assert lines[0] == "errors: 3"
        assert lines[1] == "total:  100"

    def test_empty(self):
        assert render_key_value([]) == ""
