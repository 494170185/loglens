"""M28 — repeat-burst detection: the same message hammering the log."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from loglens.model import Record

# Variable parts of a message that should not break repetition detection.
_UUID_PATTERN = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"

_NORMALIZERS = (
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<ip>"),
    (re.compile(_UUID_PATTERN), "<uuid>"),
    (re.compile(r"\d+(\.\d+)?(ms|s|m|h)?\b"), "<num>"),
)


def normalize_message(message: str) -> str:
    """Collapse variable tokens so similar lines count as the same message."""
    out = message
    for pattern, replacement in _NORMALIZERS:
        out = pattern.sub(replacement, out)
    return out.strip().lower()


@dataclass
class Burst:
    """A run of near-identical messages in a row."""

    signature: str
    example: str
    count: int
    first_seen: datetime | None
    last_seen: datetime | None
    first_line: int | None

    @property
    def duration_seconds(self) -> float:
        if self.first_seen is None or self.last_seen is None:
            return 0.0
        return (self.last_seen - self.first_seen).total_seconds()


def detect_bursts(
    records: Iterable[Record],
    min_repeat: int = 5,
) -> list[Burst]:
    """Runs of >= *min_repeat* consecutive records sharing a signature.

    Consecutive means adjacent in the input stream (stitching should run
    first so stack traces do not interleave).
    """
    bursts: list[Burst] = []
    current_sig: str | None = None
    current: list[Record] = []
    for rec in records:
        sig = normalize_message(rec.message or rec.raw.split("\n")[0])
        if sig == current_sig:
            current.append(rec)
            continue
        if current_sig is not None and len(current) >= min_repeat:
            bursts.append(_make_burst(current_sig, current))
        current_sig = sig
        current = [rec]
    if current_sig is not None and len(current) >= min_repeat:
        bursts.append(_make_burst(current_sig, current))
    return bursts


def _make_burst(signature: str, records: list[Record]) -> Burst:
    return Burst(
        signature=signature,
        example=records[0].message or records[0].raw.split("\n")[0],
        count=len(records),
        first_seen=records[0].timestamp,
        last_seen=records[-1].timestamp,
        first_line=records[0].line_no,
    )


def message_frequency(
    records: Iterable[Record],
    top: int = 10,
) -> list[tuple[str, int]]:
    """Most common normalized messages overall (not just consecutive)."""
    counts: dict[str, int] = defaultdict(int)
    for rec in records:
        counts[normalize_message(rec.message or rec.raw.split("\n")[0])] += 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:top]
