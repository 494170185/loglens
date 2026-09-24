"""M35 — Markdown report generation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from loglens.model import Record
from loglens.timebuckets import time_span
from loglens.timestamps import format_timestamp, to_utc


def _md_escape(text: str) -> str:
    """Escape pipe characters so cell contents cannot break the table."""
    return text.replace("|", "\\|").replace("\n", " ")


def _md_cell(value: object) -> str:
    from loglens.parsers.jsonl import render_value

    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if not isinstance(value, str):
        value = render_value(value)
    return _md_escape(value)


def md_table(headers: list[str], rows: Iterable[Iterable[object]]) -> str:
    """GitHub-style markdown table."""
    lines = ["| " + " | ".join(_md_escape(h) for h in headers) + " |"]
    lines.append("|" + "|".join(" :--- " for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(v) for v in row) + " |")
    return "\n".join(lines)


def md_header(text: str, level: int = 2) -> str:
    return f"{'#' * level} {text}"


def md_bullet(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


class ReportBuilder:
    """Assemble a Markdown report section by section."""

    def __init__(self, title: str):
        self.title = title
        self._sections: list[str] = [f"# {title}", ""]

    def heading(self, text: str, level: int = 2) -> ReportBuilder:
        self._sections += ["", md_header(text, level)]
        return self

    def paragraph(self, text: str) -> ReportBuilder:
        self._sections += ["", text]
        return self

    def bullets(self, items: Iterable[str]) -> ReportBuilder:
        self._sections += ["", md_bullet(items)]
        return self

    def table(self, headers: list[str], rows: Iterable[Iterable[object]]) -> ReportBuilder:
        self._sections += ["", md_table(headers, rows)]
        return self

    def code_block(self, text: str, lang: str = "") -> ReportBuilder:
        self._sections += ["", f"```{lang}", text, "```"]
        return self

    def render(self) -> str:
        return "\n".join(self._sections).rstrip() + "\n"

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(self.render(), encoding="utf-8")
        return target


def build_summary_report(
    records: list[Record],
    title: str = "loglens report",
    now: datetime | None = None,
) -> str:
    """Full one-shot markdown report over a record set."""
    now = now or datetime.now(tz=UTC)
    builder = ReportBuilder(title)
    span = time_span(records)
    builder.heading("Overview", level=2)
    overview: list[tuple[str, str]] = [("records", str(len(records)))]
    if span:
        overview += [
            ("first event", format_timestamp(span[0])),
            ("last event", format_timestamp(span[1])),
        ]
    builder.table(["field", "value"], overview)

    builder.heading("Levels", level=2)
    from loglens.aggregate import group_by

    level_rows = [
        (group.key, group.count)
        for group in sorted(
            group_by(records, "level"), key=lambda g: g.count, reverse=True
        )
        if group.key != "(missing)"
    ]
    if level_rows:
        builder.table(["level", "count"], level_rows)
    else:
        builder.paragraph("_no level information in this log_")

    builder.heading("Top messages", level=2)
    from loglens.bursts import message_frequency

    freq = message_frequency(records, top=5)
    if freq:
        builder.table(["message", "count"], [(msg, count) for msg, count in freq])
    else:
        builder.paragraph("_no messages_")

    builder.heading("Generated", level=2)
    builder.paragraph(f"_{format_timestamp(to_utc(now))}_ by loglens")
    return builder.render()
