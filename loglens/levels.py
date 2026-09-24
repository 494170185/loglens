"""M3 — severity levels: canonical names, aliases, syslog numbers."""

from __future__ import annotations

import re

_ALIASES: dict[str, str] = {
    "debug": "debug",
    "info": "info",
    "trace": "debug",
    "tracing": "debug",
    "verbose": "debug",
    "finest": "debug",
    "finer": "debug",
    "fine": "debug",
    "dbg": "debug",
    "information": "info",
    "informational": "info",
    "notice": "info",
    "log": "info",
    "std": "info",
    "inf": "info",
    "warn": "warning",
    "warning": "warning",
    "warnings": "warning",
    "attention": "warning",
    "error": "error",
    "err": "error",
    "severe": "error",
    "sev2": "error",
    "failure": "error",
    "fatal": "critical",
    "crit": "critical",
    "critical": "critical",
    "emerg": "critical",
    "panic": "critical",
    "alert": "critical",
    "sev0": "critical",
    "sev1": "critical",
    "crash": "critical",
}

CANONICAL_LEVELS = ("debug", "info", "warning", "error", "critical")

# RFC 3164/5424 numeric severities → canonical name.
SYSLOG_NUMBERS = {
    0: "critical",
    1: "critical",
    2: "critical",
    3: "error",
    4: "warning",
    5: "info",
    6: "info",
    7: "debug",
}

_LEVEL_WORD = re.compile(
    r"(?<![a-z0-9])(trace|tracing|verbose|finest|finer|fine|debug|dbg|"
    r"information(?:al)?|notice|info|log|std|inf|warn(?:ing)?(?:s)?|attention|"
    r"err(?:or)?|severe|sev[012]|failure|fatal|crit(?:ical)?|emerg|panic|alert|"
    r"crash)(?![a-z0-9])",
    re.IGNORECASE,
)


def normalize_level(value: str | int | None) -> str | None:
    """Map any spelling of a severity to its canonical name.

    Accepts common spellings (``WARNING``, ``WARN``, ``Informational``),
    numeric severities (syslog 0-7, and Python-style 10-50), and returns
    one of ``CANONICAL_LEVELS`` or ``None`` when nothing matches.
    """
    if value is None:
        return None
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        return _from_number(int(value))
    key = value.strip().strip("[]()<>:|,;").lower()
    if not key:
        return None
    if key in _ALIASES:
        return _ALIASES[key]
    # Level tokens like "lvl3", "level=4" arrive pre-stripped of "level"/"lvl".
    m = re.fullmatch(r"lvl(\d)", key)
    if m:
        return _from_number(int(m.group(1)))
    return None


def _from_number(num: int) -> str | None:
    if 0 <= num <= 7:
        return SYSLOG_NUMBERS[num]
    if num in (10, 20, 30, 40, 50):
        return {10: "debug", 20: "info", 30: "warning", 40: "error", 50: "critical"}[num]
    return None


def level_from_message(message: str) -> str | None:
    """Guess a level by looking for a severity word inside free text."""
    m = _LEVEL_WORD.search(message)
    if not m:
        return None
    return _ALIASES.get(m.group(1).lower())


def level_order(level: str | None) -> int:
    """Sort key: debug=0 … critical=4; unknown/None sorts before debug."""
    if level in CANONICAL_LEVELS:
        return CANONICAL_LEVELS.index(level)
    return -1
