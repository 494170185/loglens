"""M42g — tests for highlight and colwidth."""

from __future__ import annotations

from loglens.colwidth import clip_cell, plan_columns
from loglens.highlight import highlight, highlight_fields, highlight_regex


class TestHighlight:
    def test_case_insensitive_match(self):
        out = highlight("Error: ERROR occurred", "error")
        assert out.count("\x1b[7m") == 2

    def test_disabled_passthrough(self):
        assert highlight("abc", "b", enabled=False) == "abc"

    def test_empty_needle(self):
        assert highlight("abc", "") == "abc"

    def test_no_match_unchanged(self):
        assert highlight("abc", "xyz") == "abc"

    def test_regex_highlight(self):
        out = highlight_regex("dur=120ms", r"\d+ms")
        assert "\x1b[7m120ms\x1b[0m" in out

    def test_invalid_regex_unchanged(self):
        assert highlight_regex("text", "[broken") == "text"

    def test_multiple_fields_longest_first(self):
        out = highlight_fields("status=500 err", ["500", "err"])
        assert out.count("\x1b[7m") == 2


class TestPlanColumns:
    def test_natural_widths_fit(self):
        plan = plan_columns(["a", "b"], [["12345", "x"]], max_width=80)
        assert plan.widths == [5, 4]  # min_width floors short columns
        assert not plan.truncated

    def test_header_sets_floor(self):
        plan = plan_columns(["header"], [["x"]])
        assert plan.widths[0] == 6

    def test_shrink_widest_first(self):
        rows = [["a" * 60, "b"]]
        plan = plan_columns(["h", "h"], rows, max_width=30, min_width=4)
        assert sum(plan.widths) <= 30 - 3
        assert plan.widths[0] < 60

    def test_single_column_capped_at_max(self):
        rows = [["x" * 80]]
        plan = plan_columns(["h"], rows, max_width=10, min_width=4)
        assert plan.widths == [10]  # single column capped by max_width
        assert not plan.truncated

    def test_two_columns_shrink_to_fit(self):
        rows = [["x" * 80, "y" * 80]]
        plan = plan_columns(["h", "h"], rows, max_width=12, min_width=4)
        # 12 - gap 3 = 9 budget; 80+80 shrinks until the sum fits at 9
        assert sum(plan.widths) == 9
        assert not plan.truncated

    def test_true_truncation_when_min_floor_blocks(self):
        rows = [["x" * 80, "y" * 80]]
        # 11 - gap 3 = 8 budget, but two min-4 columns already sum to 8
        # while content still needs more -> planner gives up and flags it
        plan = plan_columns(["h", "h"], rows, max_width=11, min_width=6)
        assert plan.widths == [6, 6]
        assert plan.truncated

    def test_no_columns(self):
        plan = plan_columns([], [])
        assert plan.widths == []


class TestClipCell:
    def test_short_untouched(self):
        assert clip_cell("abc", 10) == "abc"

    def test_clipped_with_ellipsis(self):
        assert clip_cell("abcdef", 4) == "abc\u2026"

    def test_width_one(self):
        assert clip_cell("abcdef", 1) == "a"
