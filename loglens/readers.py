"""M2 — line sources with encoding fallback and position tracking."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

_ENCODINGS = ("utf-8", "latin-1")


class SourceError(Exception):
    """Raised when a source cannot be read at all."""


def decode_bytes(data: bytes, path: str | Path = "<bytes>") -> tuple[str, str]:
    """Decode *data*, trying UTF-8 first and falling back to latin-1.

    Returns ``(text, encoding)``. latin-1 maps every byte, so the fallback
    always succeeds — a mojibake line still parses instead of aborting the
    whole scan.
    """
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise SourceError(f"cannot decode {path}")  # pragma: no cover - latin-1 never fails


def read_lines(path: str | Path) -> Iterator[tuple[int, str]]:
    """Yield ``(line_no, line)`` pairs, newline-stripped, 1-based."""
    data = Path(path).read_bytes()
    text, _encoding = decode_bytes(data, path)
    for line_no, line in enumerate(iter_lines_from(text), start=1):
        yield line_no, line[1]


def iter_lines_from(data: str) -> list[tuple[int, str]]:
    """Split an in-memory string the same way ``read_lines`` splits a file."""
    lines = data.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [(i, line.rstrip("\r")) for i, line in enumerate(lines, start=1)]
