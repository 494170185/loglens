"""M34 — terminal tables with display-width alignment (CJK aware)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

_WIDE_RANGES = re.compile(
    "[\u1100-\u115f\u2329-\u232a\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe6f"
    "\uff00-\uff60\uffe0-\uffe6]"
)


def _as_text(value: object) -> str:
    """Render any scalar cell as text (None -> '', bool -> yes/no)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if not isinstance(value, str):
        from loglens.parsers.jsonl import render_value

        return render_value(value)
    return value


def display_width(text: str) -> int:
    """Column cells needed to show *text*: wide chars count as 2."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        if _WIDE_RANGES.match(ch) or unicodedata.east_asian_width(ch) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def pad_to(text: str, width: int, align: str = "left") -> str:
    """Pad *text* with spaces to *width* display columns."""
    current = display_width(text)
    if current >= width:
        return text
    fill = " " * (width - current)
    if align == "right":
        return fill + text
    if align == "center":
        left = (width - current) // 2
        return " " * left + text + " " * (width - current - left)
    return text + fill


def truncate(text: str, width: int) -> str:
    """Clip *text* to *width* display columns with an ellipsis if needed."""
    if display_width(text) <= width:
        return text
    out = ""
    used = 0
    for ch in text:
        w = 2 if (display_width(ch)) == 2 else 1
        if used + w > width - 1:
            break
        out += ch
        used += w
    return out + "\u2026"


def render_table(
    rows: Sequence[Sequence[str]],
    headers: Sequence[str] | None = None,
    aligns: Sequence[str] | None = None,
    colors: bool = False,
) -> str:
    """ASCII table with pipe separators and a header rule.

    Alignment is per column: 'left' (default), 'right' or 'center'.
    Cell widths use display width so CJK text still lines up.
    """
    body = [[_as_text(v) for v in row] for row in rows]
    table = [[_as_text(h) for h in headers], *body] if headers else body
    if not table:
        return ""
    columns = max(len(row) for row in table)
    for row in table:
        row.extend([""] * (columns - len(row)))
    if aligns is None:
        aligns = ["left"] * columns
    widths = [
        max(display_width(row[i]) for row in table) for i in range(columns)
    ]
    lines = []
    for row_index, row in enumerate(table):
        cells = [
            pad_to(row[i], widths[i], aligns[i % len(aligns)])
            for i in range(columns)
        ]
        lines.append(" | ".join(cells))
        if row_index == 0 and headers:
            lines.append("-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def render_key_value(pairs: Sequence[tuple[str, str]]) -> str:
    """Aligned ``key: value`` block for summary panels."""
    if not pairs:
        return ""
    width = max(display_width(key) for key, _ in pairs)
    return "\n".join(f"{pad_to(key + ':', width + 1)} {value}" for key, value in pairs)
