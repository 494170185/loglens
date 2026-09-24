"""M42d — byte-offset bookmarks for instant resume of parsed files."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

STATE_VERSION = 1


@dataclass
class OffsetState:
    """Where processing of one file stopped."""

    path: str
    offset: int
    line_no: int
    size: int  # file size when the offset was recorded


class OffsetStore:
    """Persist per-file offsets as JSON next to the log dir (or anywhere)."""

    def __init__(self, state_path: str | Path):
        self.state_path = Path(state_path)

    def load(self) -> dict[str, OffsetState]:
        if not self.state_path.is_file():
            return {}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if payload.get("version") != STATE_VERSION:
            return {}
        out: dict[str, OffsetState] = {}
        for entry in payload.get("files", []):
            state = OffsetState(
                path=entry["path"],
                offset=entry["offset"],
                line_no=entry["line_no"],
                size=entry["size"],
            )
            out[state.path] = state
        return out

    def save(self, states: dict[str, OffsetState]) -> None:
        payload = {
            "version": STATE_VERSION,
            "files": [asdict(s) for s in states.values()],
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def record(self, path: str | Path) -> OffsetState:
        """Current state of a file (offset = full size)."""
        p = Path(path)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        return OffsetState(path=str(path), offset=size, line_no=0, size=size)

    def is_fresh(self, state: OffsetState, path: str | Path) -> bool:
        """True when the file has not changed since *state* was recorded."""
        try:
            size = Path(path).stat().st_size
        except OSError:
            return False
        return size == state.size


def unseen_bytes(state: OffsetState, path: str | Path) -> int:
    """How many bytes arrived after the recorded offset."""
    try:
        size = Path(path).stat().st_size
    except OSError:
        return 0
    return max(0, size - state.offset)
