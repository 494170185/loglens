"""M27 — watch mode: follow a growing file from the end."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path


class FileFollower:
    """Tail-follow a file, tolerating truncation and rotation.

    Yields new complete lines as ``(line_no, line)`` pairs, starting from
    the end of the file (like ``tail -n 0 -f``). Works on Windows and
    POSIX using polling, so it has no platform-specific handles.
    """

    def __init__(self, path: str | Path, poll_interval: float = 0.2):
        self.path = Path(path)
        self.poll_interval = poll_interval
        self._offset = 0
        self._line_no = 0
        self._pending = ""

    def seek_to_end(self) -> None:
        """Start streaming from the current end of the file."""
        if self.path.exists():
            self._offset = self.path.stat().st_size
        else:
            self._offset = 0

    def poll(self) -> list[tuple[int, str]]:
        """One polling step: read new bytes and return complete lines.

        Truncation (size < offset) is detected and resets to the start of
        the file so rotated logs do not lose or duplicate content.
        """
        if not self.path.exists():
            return []
        size = self.path.stat().st_size
        if size < self._offset:
            self._offset = 0
            self._pending = ""
            self._line_no = 0
        if size == self._offset:
            return []
        with open(self.path, encoding="utf-8", errors="replace") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
            self._offset = handle.tell()
        self._pending += chunk
        lines = self._pending.split("\n")
        self._pending = lines.pop()
        out: list[tuple[int, str]] = []
        for line in lines:
            self._line_no += 1
            out.append((self._line_no, line.rstrip("\r")))
        return out

    def follow(
        self,
        on_lines: Callable[[list[tuple[int, str]]], None],
        stop: Callable[[], bool] | None = None,
        idle_limit: float | None = None,
    ) -> None:
        """Poll until *stop*() is truthy; call *on_lines* per batch.

        With *idle_limit* set, following also stops after that many
        seconds without any new data (useful in tests and CI).
        """
        self.seek_to_end()
        idle = 0.0
        while True:
            if stop is not None and stop():
                return
            lines = self.poll()
            if lines:
                idle = 0.0
                on_lines(lines)
            else:
                idle += self.poll_interval
                if idle_limit is not None and idle >= idle_limit:
                    return
            time.sleep(self.poll_interval)


def last_lines(path: str | Path, n: int = 10) -> list[str]:
    """The last *n* lines of a file without loading it whole (bounded read)."""
    data = Path(path).read_bytes()
    window = min(len(data), 1024 * 1024)
    tail = data[len(data) - window :]
    text = tail.decode("utf-8", errors="replace")
    lines = [ln for ln in text.split("\n") if ln != ""]
    return [ln.rstrip("\r") for ln in lines[-n:]]


def file_size(path: str | Path) -> int:
    try:
        return os.stat(path).st_size
    except OSError:
        return 0
