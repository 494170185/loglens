"""M9 — automatic format detection and the plain-text fallback parser."""

from __future__ import annotations

import re

from loglens.model import Record

_PLAIN_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2}[T ][0-9:.+,]+(?:Z|[+-]\d{2}:?\d{2})?)\s*"
    r"(?:\[(?P<bracket>[^\]]+)\]\s*)?"
    r"(?P<rest>.*)$"
)
_LEVEL_IN_REST = re.compile(r"^\[?(?P<level>[A-Za-z]+)\]?\s*[:\-]?\s*")


def parse_plain_line(
    line: str,
    source: str | None = None,
    line_no: int | None = None,
) -> Record | None:
    """Parse a generic ``timestamp [level] message`` line.

    Handles the common app-log shape
    ``2026-09-19 10:07:21 INFO component - message`` with optional
    bracketed logger names. Returns ``None`` when no leading timestamp
    is present — the caller then keeps the raw line as-is.
    """
    m = _PLAIN_RE.match(line)
    if not m:
        return None
    from loglens.timestamps import TimestampParser

    timestamp = TimestampParser().parse(m.group("time"))
    if timestamp is None:
        return None
    rest = m.group("rest")
    fields: dict[str, object] = {}
    level = None
    if m.group("bracket"):
        bracket = m.group("bracket")
        from loglens.levels import normalize_level

        maybe_level = normalize_level(bracket)
        if maybe_level:
            level = maybe_level
        else:
            fields["logger"] = bracket
    if level is None:
        lm = _LEVEL_IN_REST.match(rest)
        if lm:
            from loglens.levels import normalize_level

            maybe = normalize_level(lm.group("level"))
            if maybe:
                level = maybe
                rest = rest[lm.end():]
    return Record(
        raw=line,
        message=rest,
        timestamp=timestamp,
        level=level,
        fields=fields,
        source=source,
        line_no=line_no,
    )


class FormatDetector:
    """Detect which parser a stream of lines needs, with a stable result.

    The detector samples the first lines; a parser must win a majority of
    matching lines among the first ``window`` lines. Detection is cached:
    once decided, later lines are routed to the winning parser
    unconditionally (with fallback to raw on parse failure).
    """

    def __init__(self, window: int = 20):
        self.window = window
        self.format: str | None = None

    def detect(self, lines: list[str]) -> str:
        """Decide the format from a sample; returns one of the parser names.

        The result is remembered on the instance. Re-detection on the same
        instance is idempotent.
        """
        if self.format is not None:
            return self.format
        sample = lines[: self.window]
        scored = {
            "json": sum(1 for ln in sample if self._is_json(ln)),
            "access": sum(1 for ln in sample if self._is_access(ln)),
            "syslog": sum(1 for ln in sample if self._is_syslog(ln)),
            "logfmt": sum(1 for ln in sample if self._is_logfmt(ln)),
            "plain": sum(1 for ln in sample if self._is_plain(ln)),
        }
        best = max(scored, key=lambda k: scored[k])
        if scored[best] == 0:
            best = "raw"
        self.format = best
        return best

    # -- scoring helpers ------------------------------------------------------

    @staticmethod
    def _is_json(line: str) -> bool:
        from loglens.parsers.jsonl import looks_like_json

        return looks_like_json(line)

    @staticmethod
    def _is_access(line: str) -> bool:
        from loglens.parsers.access import looks_like_access

        return looks_like_access(line)

    @staticmethod
    def _is_syslog(line: str) -> bool:
        from loglens.parsers.syslog import looks_like_syslog

        return looks_like_syslog(line)

    @staticmethod
    def _is_logfmt(line: str) -> bool:
        from loglens.parsers.logfmt import looks_like_logfmt

        stripped = line.strip()
        # Guard: "key=value only" lines; quoted messages with spaces disqualify.
        return looks_like_logfmt(stripped) and "=" in stripped

    @staticmethod
    def _is_plain(line: str) -> bool:
        return parse_plain_line(line) is not None


def parse_with(format_name: str, line: str, source=None, line_no=None) -> Record:
    """Route one line to the parser named by *format_name* (with raw fallback)."""
    from loglens.parsers.access import parse_access_line
    from loglens.parsers.jsonl import parse_json_line
    from loglens.parsers.logfmt import parse_logfmt_line
    from loglens.parsers.syslog import parse_syslog_line

    rec: Record | None = None
    if format_name == "json":
        rec = parse_json_line(line, source, line_no)
    elif format_name == "access":
        rec = parse_access_line(line, source, line_no)
    elif format_name == "syslog":
        rec = parse_syslog_line(line, source, line_no)
    elif format_name == "logfmt":
        rec = parse_logfmt_line(line, source, line_no)
    elif format_name == "plain":
        rec = parse_plain_line(line, source, line_no)
    if rec is None:
        rec = Record(raw=line, message=line, source=source, line_no=line_no)
    return rec
