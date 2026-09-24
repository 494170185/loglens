"""M42g — highlight matched substrings in terminal output."""

from __future__ import annotations

import re


def highlight(text: str, needle: str, enabled: bool = True) -> str:
    """Wrap case-insensitive matches of *needle* in reverse-video ANSI."""
    if not enabled or not needle:
        return text
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    return pattern.sub(lambda m: f"\x1b[7m{m.group(0)}\x1b[0m", text)


def highlight_regex(text: str, pattern: str, enabled: bool = True) -> str:
    """Highlight a regex; invalid patterns return the text unchanged."""
    if not enabled or not pattern:
        return text
    try:
        compiled = re.compile(pattern)
    except re.error:
        return text
    return compiled.sub(lambda m: f"\x1b[7m{m.group(0)}\x1b[0m", text)


def highlight_fields(
    text: str, needles: list[str], enabled: bool = True
) -> str:
    """Highlight several needles in one pass (longest first)."""
    if not enabled or not needles:
        return text
    escaped = sorted((re.escape(n) for n in needles if n), key=len, reverse=True)
    if not escaped:
        return text
    pattern = re.compile("|".join(escaped), re.IGNORECASE)
    return pattern.sub(lambda m: f"\x1b[7m{m.group(0)}\x1b[0m", text)
