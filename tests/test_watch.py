"""M27 — watch mode."""

from __future__ import annotations

import time
from pathlib import Path

from loglens.watch import FileFollower, last_lines


class TestPoll:
    def test_reads_new_lines_incrementally(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text("old line\n", encoding="utf-8")
        follower = FileFollower(f)
        follower.seek_to_end()
        assert follower.poll() == []

        with open(f, "a", encoding="utf-8") as handle:
            handle.write("new one\nnew two\n")
        lines = follower.poll()
        assert lines == [(1, "new one"), (2, "new two")]

    def test_partial_line_held_until_complete(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text("", encoding="utf-8")
        follower = FileFollower(f)
        follower.seek_to_end()
        with open(f, "a", encoding="utf-8") as handle:
            handle.write("partial")
        assert follower.poll() == []
        with open(f, "a", encoding="utf-8") as handle:
            handle.write(" done\n")
        assert follower.poll() == [(1, "partial done")]

    def test_truncation_resets(self, tmp_path: Path):
        f = tmp_path / "rotated.log"
        f.write_text("a" * 500 + "\n", encoding="utf-8")
        follower = FileFollower(f)
        follower.seek_to_end()
        # rotate: file shrinks
        f.write_text("fresh\n", encoding="utf-8")
        lines = follower.poll()
        assert lines == [(1, "fresh")]

    def test_missing_file_is_noop(self, tmp_path: Path):
        follower = FileFollower(tmp_path / "ghost.log")
        follower.seek_to_end()
        assert follower.poll() == []


class TestFollow:
    def test_follow_stops_on_idle(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text("seed\n", encoding="utf-8")
        follower = FileFollower(f, poll_interval=0.01)
        collected: list[tuple[int, str]] = []

        def on_lines(lines):
            collected.extend(lines)

        start = time.monotonic()
        follower.follow(on_lines, idle_limit=0.1)
        elapsed = time.monotonic() - start
        assert elapsed < 2
        # seed line predates seek_to_end, so nothing is collected
        assert collected == []

    def test_follow_collects_appended(self, tmp_path: Path):
        f = tmp_path / "app.log"
        f.write_text("", encoding="utf-8")
        follower = FileFollower(f, poll_interval=0.01)
        collected: list[tuple[int, str]] = []

        import threading

        def writer():
            time.sleep(0.05)
            with open(f, "a", encoding="utf-8") as handle:
                handle.write("hello\n")

        thread = threading.Thread(target=writer)
        thread.start()
        follower.follow(lambda lines: collected.extend(lines), idle_limit=0.3)
        thread.join()
        assert collected == [(1, "hello")]

    def test_follow_stop_callback(self, tmp_path: Path):
        f = tmp_path / "app.log"
        follower = FileFollower(f, poll_interval=0.01)
        follower.seek_to_end()
        follower.follow(lambda _lines: None, stop=lambda: True)
        # returns immediately without error


class TestLastLines:
    def test_last_n(self, tmp_path: Path):
        f = tmp_path / "x.log"
        f.write_text("\n".join(f"line{i}" for i in range(100)) + "\n", encoding="utf-8")
        assert last_lines(f, 3) == ["line97", "line98", "line99"]

    def test_fewer_available(self, tmp_path: Path):
        f = tmp_path / "y.log"
        f.write_text("a\nb\n", encoding="utf-8")
        assert last_lines(f, 10) == ["a", "b"]

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "z.log"
        f.write_text("", encoding="utf-8")
        assert last_lines(f, 5) == []
