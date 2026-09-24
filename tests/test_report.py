"""M35 — Markdown reports."""

from __future__ import annotations

from datetime import UTC, datetime

from loglens.model import Record
from loglens.report import (
    ReportBuilder,
    build_summary_report,
    md_bullet,
    md_header,
    md_table,
)


def rec(message, level=None, ts=None):
    return Record(raw=message, message=message, level=level, timestamp=ts)


class TestMdPrimitives:
    def test_header(self):
        assert md_header("Section", level=2) == "## Section"

    def test_bullet_list(self):
        assert md_bullet(["a", "b"]) == "- a\n- b"

    def test_table_shape(self):
        text = md_table(["a", "b"], [(1, "x"), (2, "y")])
        lines = text.split("\n")
        assert lines[0] == "| a | b |"
        assert lines[1].startswith("| :--- | :--- |")
        assert lines[2] == "| 1 | x |"

    def test_pipe_escaped(self):
        text = md_table(["h"], [("a|b",)])
        assert "a\\|b" in text

    def test_newline_in_cell_replaced(self):
        text = md_table(["h"], [("line1\nline2",)])
        assert "\n" not in text.split("\n")[2]

    def test_none_renders_empty(self):
        assert md_table(["h"], [(None,)]) .split("\n")[2] == "|  |"

    def test_bool_renders_yes_no(self):
        text = md_table(["h"], [(True,), (False,)])
        lines = text.split("\n")
        assert "yes" in lines[2]
        assert "no" in lines[3]


class TestReportBuilder:
    def test_fluent_chain(self):
        report = (
            ReportBuilder("Demo")
            .heading("Sec")
            .paragraph("hello")
            .bullets(["one", "two"])
            .table(["h"], [(1,)])
            .code_block("plain\ntext")
            .render()
        )
        assert report.startswith("# Demo")
        assert "## Sec" in report
        assert "- one" in report
        assert "| h |" in report
        assert "```" in report

    def test_render_trailing_newline(self):
        assert ReportBuilder("T").render().endswith("\n")

    def test_save(self, tmp_path):
        out = tmp_path / "r.md"
        ReportBuilder("T").paragraph("x").save(out)
        content = out.read_text(encoding="utf-8")
        assert content.startswith("# T")


class TestSummaryReport:
    def test_full_report(self):
        base = datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC)
        records = [
            rec("timeout connecting", "error", base),
            rec("timeout connecting", "error", base),
            rec("request served", "info", base),
        ]
        text = build_summary_report(records, now=base)
        assert "# loglens report" in text
        assert "## Overview" in text
        assert "## Levels" in text
        assert "error" in text
        assert "## Top messages" in text
        assert "timeout connecting" in text

    def test_empty_log(self):
        text = build_summary_report([], now=datetime(2026, 9, 19, tzinfo=UTC))
        assert "| records | 0 |" in text
        assert "no level information" in text

    def test_no_timestamps_section_omitted(self):
        records = [rec("only message")]
        text = build_summary_report(records)
        assert "first event" not in text
