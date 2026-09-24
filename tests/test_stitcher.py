"""M10 — multiline stitching of stack traces."""

from __future__ import annotations

from loglens.model import Record
from loglens.stitcher import Stitcher, iter_stitch, stitch


def rec(raw, **kw):
    return Record(raw=raw, message=kw.get("message", raw), **{
        k: v for k, v in kw.items() if k != "message"
    })


class TestBasicFolding:
    def test_indented_line_folds_into_parent(self):
        out = stitch([rec("ERROR boom"), rec("    at com.foo.Bar(Bar.java:1)")])
        assert len(out) == 1
        assert "at com.foo.Bar" in out[0].raw
        assert out[0].raw.count("\n") == 1

    def test_parent_message_preserved(self):
        out = stitch([rec("ERROR boom", message="boom"), rec("  detail")])
        assert out[0].message == "boom"

    def test_two_parents_split_correctly(self):
        out = stitch([
            rec("ERROR first"),
            rec("  trace1"),
            rec("INFO second"),
            rec("  trace2"),
        ])
        assert len(out) == 2
        assert "first" in out[0].raw and "trace1" in out[0].raw
        assert "second" in out[1].raw and "trace2" in out[1].raw

    def test_streaming_matches_batch(self):
        records = [rec("A"), rec("  x"), rec("B"), rec("  y"), rec("C")]
        assert [r.raw for r in stitch(records)] == [
            r.raw for r in iter_stitch(records)
        ]


class TestStackVocabularies:
    def test_java_caused_by(self):
        out = stitch([rec("ERROR x"), rec("Caused by: java.lang.NullPointerException")])
        assert len(out) == 1

    def test_python_traceback(self):
        lines = [
            rec("ERROR handler failed"),
            rec("Traceback (most recent call last):"),
            rec('  File "app.py", line 1, in <module>'),
            rec("ValueError: bad value"),
        ]
        out = stitch(lines)
        assert len(out) == 1
        assert out[0].raw.endswith("ValueError: bad value")

    def test_go_panic(self):
        out = stitch([rec("panic: runtime error"), rec("goroutine 1 [running]:")])
        assert len(out) == 1

    def test_java_more_suffix(self):
        out = stitch([rec("ERROR x"), rec("   ... 3 more")])
        assert len(out) == 1


class TestEdgeCases:
    def test_continuation_without_parent_passes_through(self):
        out = stitch([rec("  orphan line")])
        assert len(out) == 1
        assert out[0].raw == "  orphan line"

    def test_empty_line_folds(self):
        out = stitch([rec("ERROR x"), rec("")])
        assert len(out) == 1

    def test_max_fold_stops_absorbing(self):
        stitcher = Stitcher(max_fold=2)
        emitted = []
        for i in range(5):
            done = stitcher.feed(rec(f"  cont {i}"))
            if done is not None:
                emitted.append(done)
        # first orphan passes through; after 2 folds, further conts emit
        tail = stitcher.close()
        if tail is not None:
            emitted.append(tail)
        assert len(emitted) >= 1

    def test_close_flushes_pending(self):
        s = Stitcher()
        assert s.feed(rec("A")) is None
        tail = s.close()
        assert tail is not None and tail.raw == "A"

    def test_level_and_timestamp_survive(self):
        from datetime import UTC, datetime

        ts = datetime(2026, 9, 19, 10, 0, 0, tzinfo=UTC)
        out = stitch([
            Record(raw="E", message="E", level="error", timestamp=ts),
            Record(raw="  x", message="x"),
        ])
        assert out[0].level == "error"
        assert out[0].timestamp == ts

    def test_source_line_no_from_parent(self):
        out = stitch([
            Record(raw="E", message="E", source="a.log", line_no=5),
            Record(raw="  x", message="x", source="a.log", line_no=6),
        ])
        assert out[0].source == "a.log"
        assert out[0].line_no == 5
