"""M33 — ANSI terminal colors with NO_COLOR support."""

from __future__ import annotations

import os
import re

_RESET = "\x1b[0m"

_CODES = {
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "blue": "\x1b[34m",
    "magenta": "\x1b[35m",
    "cyan": "\x1b[36m",
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
}


def colors_enabled(stream_is_tty: bool | None = None, env: dict[str, str] | None = None) -> bool:
    """Decide whether ANSI codes should be emitted.

    Honors ``NO_COLOR`` and ``TERM=dumb``; a non-tty stream disables
    colors unless ``FORCE_COLOR`` is set.
    """
    env = env if env is not None else dict(os.environ)
    if stream_is_tty is None:
        stream_is_tty = False
    if env.get("NO_COLOR"):
        return False
    if env.get("FORCE_COLOR"):
        return True
    if env.get("TERM") == "dumb":
        return False
    return stream_is_tty


def paint(text: str, *styles: str, enabled: bool = True) -> str:
    """Wrap *text* in ANSI codes for each style name, in order."""
    if not enabled or not text:
        return text
    prefix = "".join(_CODES[style] for style in styles if style in _CODES)
    if not prefix:
        return text
    return f"{prefix}{text}{_RESET}"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


LEVEL_COLORS = {
    "critical": "red",
    "error": "red",
    "warning": "yellow",
    "info": "cyan",
    "debug": "dim",
}


def level_style(level: str | None) -> str:
    """Color name for a severity level."""
    return LEVEL_COLORS.get(level or "", "green")


def paint_level(level: str | None, enabled: bool = True) -> str:
    """Render a level label in its conventional color."""
    if not level:
        return ""
    return paint(level.upper(), level_style(level), enabled=enabled)
