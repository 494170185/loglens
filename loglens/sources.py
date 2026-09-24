"""M23/M24 — gzip-transparent sources and multi-file merging."""

from __future__ import annotations

import gzip
import io
from collections.abc import Iterator
from pathlib import Path

from loglens.model import Record
from loglens.readers import decode_bytes, iter_lines_from


def read_lines_any(path: str | Path) -> Iterator[tuple[int, str]]:
    """Line iterator over plain or gzipped text files, detected by magic bytes.

    A file is treated as gzip when its first two bytes are ``1f 8b``;
    the ``.gz`` extension alone is not trusted.
    """
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    text, _encoding = decode_bytes(data, path)
    yield from enumerate((line for _i, line in iter_lines_from(text)), start=1)


def is_gzip(path: str | Path) -> bool:
    """True when *path* starts with the gzip magic bytes."""
    with open(path, "rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


def read_lines_iterable(source: str) -> Iterator[tuple[int, str]]:
    """Line iterator over an in-memory string (for tests and watch mode)."""
    yield from enumerate((line for _i, line in iter_lines_from(source)), start=1)


class MergedSource:
    """Merge already-parsed record streams ordered by timestamp.

    Later files' records keep their own ``source``; ordering is stable:
    when timestamps tie (or are missing), arrival order wins.
    """

    def merge(self, streams: list[list[Record]]) -> list[Record]:
        """K-way merge by (timestamp present, timestamp, arrival index)."""
        import heapq

        heap: list[tuple[int, int, Record]] = []
        arrival = 0
        for stream in streams:
            for record in stream:
                key = _sort_key(record)
                heapq.heappush(heap, (key, arrival, record))
                arrival += 1
        out: list[Record] = []
        while heap:
            _key, _arrival, record = heapq.heappop(heap)
            out.append(record)
        return out


def _sort_key(record: Record) -> int:
    """Records without timestamps sort to the end, keeping file blocks."""
    if record.timestamp is None:
        return 2**62
    from loglens.timestamps import to_utc

    return int(to_utc(record.timestamp).timestamp())


def merge_files(
    paths: list[str | Path],
    parse_one: callable,
) -> list[Record]:
    """Read several files (any mix of plain/gzip) and time-merge records.

    *parse_one* is a callable ``(path) -> list[Record]`` (typically
    ``Collector().collect_file``).
    """
    merger = MergedSource()
    streams = [parse_one(path) for path in paths]
    return merger.merge(streams)


def normalize_paths(patterns: list[str]) -> list[Path]:
    """Expand glob patterns and directories into a concrete file list.

    Directories contribute ``*.log`` and ``*.log.gz`` (non-recursive).
    Duplicates are removed while preserving order.
    """
    import glob

    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in patterns:
        p = Path(pattern)
        if p.is_dir():
            candidates: list[Path] = []
            for name in ("*.log", "*.log.gz", "*.txt"):
                candidates.extend(sorted(p.glob(name)))
        elif any(ch in pattern for ch in "*?["):
            candidates = [Path(m) for m in sorted(glob.glob(pattern))]
        else:
            candidates = [p]
        for candidate in candidates:
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            out.append(candidate)
    return out


def gunzip_bytes(data: bytes) -> bytes:
    """Decompress gzip bytes; passthrough when not gzip."""
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def gzip_bytes(data: bytes) -> bytes:
    """Compress bytes to gzip (test helper)."""
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb") as gz:
        gz.write(data)
    return out.getvalue()
