"""M2 — line sources with encoding fallback and position tracking."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

_ENCODINGS = ("utf-8", "latin-1")


class SourceError(Exception):
    """Raised when a source cannot be read at all."""


def open_text(path: str | Path):
    """Open *path* as text, falling back to latin-1 for non-UTF-8 bytes.

    latin-1 never fails, so a mojibake line still parses instead of
    aborting a whole scan; the encoding that worked is exposed on the
    file object as ``encoding``.
    """
    last_error: UnicodeDecodeError | None = None
    for encoding in _ENCODINGS:
        try:
            return open(path, encoding=encoding, errors=None)
        except UnicodeDecodeError as exc:  # pragma: no cover - exercised via read_lines
            last_error = exc
    raise SourceError(f"cannot decode {path}: {last_error}")


def read_lines(path: str | Path) -> Iterator[tuple[int, str]]:
    """Yield ``(line_no, line)`` pairs, newline-stripped, 1-based."""
    handle = open_text(path)
    with handle:
        for line_no, line in enumerate(handle, start=1):
            if line.endswith("\r\n"):
                line = line[:-2]
            elif line.endswith(("\n", "\r")):
                line = line[:-1]
            yield line_no, line


def iter_lines_from(data: str) -> list[tuple[int, str]]:
    """Split an in-memory string the same way ``read_lines`` splits a file."""
    lines = data.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [(i, line.rstrip("\r")) for i, line in enumerate(lines, start=1)]
