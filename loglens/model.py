"""Core record model shared by every parser and stage."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime


@dataclass
class Record:
    """One parsed log entry.

    Attributes:
        raw: the original line (without trailing newline).
        message: the human-readable body; for structured formats this is the
            rendered message field when available, otherwise the raw line.
        timestamp: parsed timestamp, or None when the format carries none.
        level: normalized severity label (``debug``..``critical``) or None.
        fields: structured key/value pairs extracted from the line.
        source: originating file path, when known.
        line_no: 1-based line number in the source, when known.
    """

    raw: str
    message: str = ""
    timestamp: datetime | None = None
    level: str | None = None
    fields: dict[str, object] = field(default_factory=dict)
    source: str | None = None
    line_no: int | None = None

    def with_message(self, message: str) -> Record:
        return replace(self, message=message)

    def merged(self, extra: dict[str, object]) -> Record:
        fields = dict(self.fields)
        fields.update(extra)
        return replace(self, fields=fields)

    def get(self, key: str, default: object = None) -> object:
        if key in self.fields:
            return self.fields[key]
        if key == "message":
            return self.message
        if key == "level":
            return self.level
        if key == "timestamp":
            return self.timestamp
        return default

    def __getitem__(self, key: str) -> object:
        value = self.get(key, KeyError)
        if value is KeyError:
            raise KeyError(key)
        return value

    def __contains__(self, key: str) -> bool:
        return self.get(key, KeyError) is not KeyError
