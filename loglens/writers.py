"""M32 — record writers: text, JSON lines, JSON array, CSV."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from pathlib import Path

from loglens.model import Record
from loglens.timestamps import to_utc


def record_to_dict(record: Record) -> dict[str, object]:
    """Flat JSON-ready mapping of a record."""
    out: dict[str, object] = {
        "raw": record.raw,
        "message": record.message,
    }
    if record.timestamp is not None:
        out["timestamp"] = to_utc(record.timestamp).isoformat()
    if record.level is not None:
        out["level"] = record.level
    if record.source is not None:
        out["source"] = record.source
    if record.line_no is not None:
        out["line_no"] = record.line_no
    for key, value in record.fields.items():
        out[f"f_{key}"] = value
    return out


def write_text(records: Iterable[Record]) -> str:
    """Plain text: the raw lines, newline separated."""
    return "\n".join(rec.raw for rec in records)


def write_jsonl(records: Iterable[Record]) -> str:
    """One JSON object per line."""
    return "\n".join(
        json.dumps(record_to_dict(rec), ensure_ascii=False, default=str)
        for rec in records
    )


def write_json(records: Iterable[Record], indent: int = 2) -> str:
    """A single JSON array of record objects."""
    return json.dumps(
        [record_to_dict(rec) for rec in records],
        ensure_ascii=False,
        indent=indent,
        default=str,
    )


def write_csv(records: Iterable[Record], columns: list[str] | None = None) -> str:
    """CSV export; *columns* selects fields (default: common set)."""
    if columns is None:
        columns = ["timestamp", "level", "message", "source", "line_no"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for rec in records:
        row = []
        for col in columns:
            if col.startswith("f_"):
                value = rec.fields.get(col[2:], "")
            elif col == "timestamp":
                value = to_utc(rec.timestamp).isoformat() if rec.timestamp else ""
            else:
                value = getattr(rec, col, "") or ""
            if isinstance(value, bool):
                value = "true" if value else "false"
            row.append(value)
        writer.writerow(row)
    return buffer.getvalue()


def write_records(
    records: Iterable[Record],
    fmt: str,
    path: Path | None = None,
) -> str:
    """Render records as *fmt* ('text'|'json'|'jsonl'|'csv') and optionally save."""
    materialized = list(records)
    if fmt == "text":
        text = write_text(materialized)
    elif fmt == "jsonl":
        text = write_jsonl(materialized)
    elif fmt == "json":
        text = write_json(materialized)
    elif fmt == "csv":
        text = write_csv(materialized)
    else:
        raise ValueError(f"unknown output format {fmt!r}")
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def read_jsonl(text: str) -> list[dict[str, object]]:
    """Parse written JSONL back (round-trip helper for tests)."""
    return [json.loads(line) for line in text.split("\n") if line]
