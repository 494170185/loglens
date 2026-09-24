"""M12 — the collect pipeline: file to stitched, enriched records."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from loglens.model import Record
from loglens.parsers.detect import FormatDetector, parse_with
from loglens.readers import read_lines
from loglens.stitcher import Stitcher


class CollectionStats:
    """Counters describing one collection run."""

    def __init__(self) -> None:
        self.lines_read = 0
        self.records_emitted = 0
        self.continuations_folded = 0
        self.format = "raw"

    def as_dict(self) -> dict[str, object]:
        return {
            "lines_read": self.lines_read,
            "records_emitted": self.records_emitted,
            "continuations_folded": self.continuations_folded,
            "format": self.format,
        }


class Collector:
    """Stream a log file into records: detect, parse, stitch, enrich."""

    def __init__(
        self,
        enrich: bool = True,
        stitch: bool = True,
        detect_window: int = 20,
    ):
        self.enrich_enabled = enrich
        self.stitch_enabled = stitch
        self.detect_window = detect_window

    def collect_file(self, path: str | Path, fmt: str | None = None) -> list[Record]:
        return list(self.iter_file(path, fmt))

    def iter_file(self, path: str | Path, fmt: str | None = None) -> Iterator[Record]:
        """Yield records from *path*; format auto-detected unless given."""
        path = Path(path)
        raw_lines = [line for _no, line in read_lines(path)]
        if fmt is None:
            fmt = FormatDetector(window=self.detect_window).detect(raw_lines)
        yield from self._run(raw_lines, fmt, source=str(path))

    def collect_lines(self, lines: list[str], fmt: str | None = None) -> list[Record]:
        if fmt is None:
            fmt = FormatDetector(window=self.detect_window).detect(lines)
        return list(self._run(lines, fmt, source=None))

    def _run(self, lines: list[str], fmt: str, source: str | None) -> Iterator[Record]:
        stitcher = Stitcher() if self.stitch_enabled else _NoopStitcher()
        stats = CollectionStats()
        stats.format = fmt
        for line_no, line in enumerate(lines, start=1):
            stats.lines_read += 1
            record = parse_with(fmt, line, source=source, line_no=line_no)
            done = stitcher.feed(record)
            if done is not None:
                stats.records_emitted += 1
                if "\n" in done.raw:
                    stats.continuations_folded += done.raw.count("\n")
                yield self._finish(done)
        tail = stitcher.close()
        if tail is not None:
            stats.records_emitted += 1
            if "\n" in tail.raw:
                stats.continuations_folded += tail.raw.count("\n")
            yield self._finish(tail)
        self.last_stats = stats

    def _finish(self, record: Record) -> Record:
        if self.enrich_enabled:
            from loglens.extract import enrich

            return enrich(record)
        return record


class _NoopStitcher:
    """Stitcher stand-in that emits every record unchanged."""

    def feed(self, record: Record) -> Record:
        return record

    def close(self) -> Record | None:
        return None
