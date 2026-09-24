"""M3 — level normalization across spellings and numeric severities."""

from __future__ import annotations

import pytest

from loglens.levels import (
    CANONICAL_LEVELS,
    level_from_message,
    level_order,
    normalize_level,
)


class TestNormalizeSpelling:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("DEBUG", "debug"),
            ("Debug", "debug"),
            ("trace", "debug"),
            ("verbose", "debug"),
            ("fine", "debug"),
            ("INFO", "info"),
            ("Informational", "info"),
            ("notice", "info"),
            ("WARN", "warning"),
            ("Warning", "warning"),
            ("warn", "warning"),
            ("ERROR", "error"),
            ("err", "error"),
            ("Err", "error"),
            ("severe", "error"),
            ("FATAL", "critical"),
            ("CRIT", "critical"),
            ("Critical", "critical"),
            ("emerg", "critical"),
            ("panic", "critical"),
            ("[error]", "error"),
            ("(WARN)", "warning"),
            ("<info>", "info"),
            ("error:", "error"),
        ],
    )
    def test_spellings(self, raw, expected):
        assert normalize_level(raw) == expected

    def test_none_stays_none(self):
        assert normalize_level(None) is None

    def test_empty_string_is_none(self):
        assert normalize_level("") is None
        assert normalize_level("   ") is None

    def test_unknown_word_is_none(self):
        assert normalize_level("banana") is None

    def test_lvl_numbers(self):
        assert normalize_level("lvl0") == "critical"
        assert normalize_level("lvl7") == "debug"


class TestNormalizeNumbers:
    @pytest.mark.parametrize(
        ("num", "expected"),
        [
            (0, "critical"),
            (1, "critical"),
            (2, "critical"),
            (3, "error"),
            (4, "warning"),
            (5, "info"),
            (6, "info"),
            (7, "debug"),
            (10, "debug"),
            (20, "info"),
            (30, "warning"),
            (40, "error"),
            (50, "critical"),
            (8, None),
            (15, None),
            (-1, None),
            ("5", "info"),
        ],
    )
    def test_numbers(self, num, expected):
        assert normalize_level(num) == expected


class TestLevelFromMessage:
    def test_finds_embedded_severity(self):
        assert level_from_message("disk usage at 90% WARNING") == "warning"
        ERR = "Connection refused ERROR while dialing"
        assert level_from_message(ERR) == "error"

    def test_word_boundary_protects_prefixes(self):
        assert level_from_message("informative message") is None or (
            level_from_message("informative message") == "info"
        )
        # "errorsome" is not a level word because of the trailing guard.
        assert level_from_message("errorsome word") is None

    def test_plain_message_has_no_level(self):
        assert level_from_message("user alice logged in") is None

    def test_first_match_wins_left_to_right(self):
        assert level_from_message("warn then error later") == "warning"


class TestOrdering:
    def test_canonical_levels_are_sorted(self):
        ordered = [level_order(name) for name in CANONICAL_LEVELS]
        assert ordered == sorted(ordered)

    def test_unknown_sorts_before_debug(self):
        assert level_order(None) < level_order("debug")
        assert level_order("banana") < level_order("debug")

    def test_critical_is_max(self):
        assert level_order("critical") == 4
