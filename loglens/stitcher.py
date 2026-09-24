"""M10 — multiline stitching: fold stack traces into their parent record."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from loglens.model import Record

# Lines that begin like a continuation of a stack trace or exception dump.
_CONTINUATION_RE = re.compile(
    r"""^(
        \s+at\s                                   # Java: '    at com.foo.Bar(...)'
      | \s*\.\.\.\s*\d+\s*more                    # Java: '... 3 more'
      | Caused\ by:                               # Java nested exception
      | Traceback\ \(most\ recent\ call\ last\)   # Python header
      | \s+File\ "                                # Python frame
      | raise\s                                   # Python raise line
      | [A-Za-z_][\w.]*Error(?::|\s)              # bare exception class line
      | [A-Za-z_][\w.]*Exception(?::|\s)
      | goroutine\s\d+                            # Go panic header
      | panic\(                                   # Go panic
      | \s+\.\.\.$
    )""",
    re.VERBOSE,
)


class Stitcher:
    """Fold continuation lines into the most recent parent record.

    A line is a continuation when it starts with whitespace, matches the
    stack-trace vocabulary above, or both. Parents emit only when a new
    non-continuation line arrives (or on close), so every record carries a
    complete ``raw`` including its folded lines.
    """

    def __init__(self, max_fold: int = 200):
        self.max_fold = max_fold
        self._pending: Record | None = None
        self._folded = 0

    def feed(self, record: Record) -> Record | None:
        """Feed one record; returns a completed parent or ``None``.

        When *record* is a continuation it is folded into the pending
        parent and ``None`` is returned.
        """
        if self._pending is None:
            if self._is_continuation(record):
                # Continuation without a parent: pass through unchanged.
                return record
            self._pending = record
            self._folded = 0
            return None
        if self._is_continuation(record) and self._folded < self.max_fold:
            parent = self._pending
            self._pending = Record(
                raw=parent.raw + "\n" + record.raw,
                message=parent.message,
                timestamp=parent.timestamp,
                level=parent.level,
                fields=parent.fields,
                source=record.source or parent.source,
                line_no=parent.line_no,
            )
            self._folded += 1
            return None
        done = self._pending
        self._pending = record
        self._folded = 0
        return done

    def close(self) -> Record | None:
        """Flush the pending parent at end of stream."""
        done = self._pending
        self._pending = None
        return done

    @staticmethod
    def _is_continuation(record: Record) -> bool:
        line = record.raw
        if not line:
            return True
        if line[:1] in (" ", "\t"):
            return True
        return bool(_CONTINUATION_RE.match(line))


def stitch(records: Iterable[Record]) -> list[Record]:
    """Convenience wrapper: stitch an entire record stream."""
    stitcher = Stitcher()
    out: list[Record] = []
    for rec in records:
        done = stitcher.feed(rec)
        if done is not None:
            out.append(done)
    tail = stitcher.close()
    if tail is not None:
        out.append(tail)
    return out


def iter_stitch(records: Iterable[Record]) -> Iterator[Record]:
    """Streaming variant of :func:`stitch` for pipeline use."""
    stitcher = Stitcher()
    for rec in records:
        done = stitcher.feed(rec)
        if done is not None:
            yield done
    tail = stitcher.close()
    if tail is not None:
        yield tail
