"""M31 — sessionization: group records into per-client sessions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from loglens.model import Record
from loglens.timestamps import to_utc

DEFAULT_IDLE_TIMEOUT = timedelta(minutes=30)


@dataclass
class Session:
    """Consecutive records from one key within an idle timeout."""

    key: str
    records: list[Record] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def start(self) -> datetime | None:
        stamps = [to_utc(r.timestamp) for r in self.records if r.timestamp]
        return min(stamps) if stamps else None

    @property
    def end(self) -> datetime | None:
        stamps = [to_utc(r.timestamp) for r in self.records if r.timestamp]
        return max(stamps) if stamps else None

    @property
    def duration(self) -> timedelta | None:
        if self.start is None or self.end is None:
            return None
        return self.end - self.start

    def events(self, name: str) -> list[object]:
        return [r.get(name) for r in self.records]

    def summary_line(self) -> str:
        start = self.start.strftime("%H:%M:%S") if self.start else "--:--:--"
        end = self.end.strftime("%H:%M:%S") if self.end else "--:--:--"
        return f"{self.key}: {self.count} events {start}..{end}"


def sessionize(
    records: Iterable[Record],
    key_field: str = "client",
    idle_timeout: timedelta = DEFAULT_IDLE_TIMEOUT,
) -> list[Session]:
    """Split a time-sorted stream into sessions per key.

    A session ends when the same key is silent for *idle_timeout* or when
    the stream ends. Records without the key field are skipped; records
    without timestamps never start a new session (they attach to the
    current one if it exists).
    """
    from loglens.aggregate import field_value

    sessions: list[Session] = []
    current: dict[str, Session] = {}
    last_active: dict[str, datetime] = {}
    for rec in records:
        key_value = field_value(rec, key_field)
        if key_value is None:
            continue
        key = str(key_value)
        stamp = to_utc(rec.timestamp) if rec.timestamp else None
        if (
            key in current
            and stamp is not None
            and key in last_active
            and stamp - last_active[key] > idle_timeout
        ):
            del current[key]
        if key not in current:
            current[key] = Session(key=key)
            sessions.append(current[key])
        current[key].records.append(rec)
        if stamp is not None:
            last_active[key] = stamp
    return sessions


def session_durations(sessions: list[Session]) -> list[float]:
    """Session durations in seconds (timestamp-less sessions excluded)."""
    out = []
    for s in sessions:
        if s.duration is not None:
            out.append(s.duration.total_seconds())
    return out


def longest_sessions(sessions: list[Session], top: int = 5) -> list[Session]:
    """Sessions with the most events (ties broken by key order)."""
    ranked = sorted(sessions, key=lambda s: s.count, reverse=True)
    return ranked[:top]
