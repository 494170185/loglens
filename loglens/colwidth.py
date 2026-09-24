"""M42g — column width strategy for wide tables."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ColumnPlan:
    """Computed widths for one rendered table."""

    headers: list[str]
    widths: list[int]
    total_width: int
    truncated: bool


def plan_columns(
    headers: list[str],
    sample_rows: list[list[str]],
    max_width: int = 120,
    min_width: int = 4,
    gap: int = 3,
) -> ColumnPlan:
    """Distribute a character budget across columns.

    Columns start at their natural content width (capped by *max_width*).
    If the total exceeds the budget, the widest columns shrink first,
    never below *min_width*.
    """
    columns = len(headers)
    if columns == 0:
        return ColumnPlan(headers=[], widths=[], total_width=0, truncated=False)
    natural = [min_width] * columns
    for i, header in enumerate(headers):
        natural[i] = max(natural[i], len(header))
    for row in sample_rows:
        for i in range(min(len(row), columns)):
            natural[i] = max(natural[i], len(str(row[i])))
    budget = max_width - gap * (columns - 1)
    widths = [min(w, max_width) for w in natural]
    total = sum(widths)
    truncated = False
    while total > budget:
        # shrink the widest column by one, but not below min_width
        candidates = [i for i, w in enumerate(widths) if w > min_width]
        if not candidates:
            truncated = True
            break
        widest = max(candidates, key=lambda i: widths[i])
        widths[widest] -= 1
        total -= 1
    return ColumnPlan(
        headers=headers, widths=widths, total_width=total, truncated=truncated
    )


def clip_cell(text: str, width: int) -> str:
    """Clip a cell to *width* characters with an ellipsis."""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "\u2026"
