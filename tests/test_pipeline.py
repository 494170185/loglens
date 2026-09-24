"""M40 — streaming pipeline."""

from __future__ import annotations

from loglens.model import Record
from loglens.pipeline import (
    Pipeline,
    PipelineStats,
    stage_dedup,
    stage_filter,
    stage_limit,
    stage_map,
    stage_min_level,
    stage_offset,
    stage_sample_every,
    stage_stats,
)


def rec(level=None, msg="", **fields):
    return Record(raw=msg, message=msg, level=level, fields=fields)


class TestChaining:
    def test_stages_run_in_order(self):
        pipeline = Pipeline().then(stage_offset(1)).then(stage_limit(2))
        out = pipeline.run([rec(msg="a"), rec(msg="b"), rec(msg="c"), rec(msg="d")])
        assert [r.message for r in out] == ["b", "c"]

    def test_empty_pipeline_passthrough(self):
        assert [r.message for r in Pipeline().run([rec(msg="x")])] == ["x"]

    def test_lazy_single_pass(self):
        reads: list[str] = []

        def source():
            for name in ("a", "b", "c"):
                reads.append(name)
                yield rec(msg=name)

        pipeline = Pipeline().then(stage_limit(2))
        it = pipeline.iter(source())
        first = next(it)
        assert first.message == "a"
        # pulling one item must not exhaust the source
        assert "b" not in reads or reads == ["a", "b"]
        rest = list(it)
        assert [r.message for r in rest] == ["b"]
        # limit(2) stops pulling after its quota; 'c' may or may not be read
        assert set(reads) <= {"a", "b", "c"}

    def test_add_returns_self(self):
        p = Pipeline()
        assert p.add(stage_limit(1)) is p


class TestStages:
    def test_filter(self):
        out = stage_filter(lambda r: r.level == "error")(
            iter([rec("error"), rec("info")])
        )
        assert [r.level for r in out] == ["error"]

    def test_limit(self):
        out = list(stage_limit(2)(iter([rec(), rec(), rec()])))
        assert len(out) == 2

    def test_offset(self):
        out = list(stage_offset(2)(iter([rec(msg="a"), rec(msg="b"), rec(msg="c")])))
        assert [r.message for r in out] == ["c"]

    def test_map(self):
        out = list(stage_map(lambda r: r.with_message("z"))(iter([rec(msg="a")])))
        assert out[0].message == "z"

    def test_dedup(self):
        records = [rec(msg="x", i=1), rec(msg="x", i=2), rec(msg="y", i=3)]
        out = list(stage_dedup(lambda r: r.message)(iter(records)))
        assert len(out) == 2

    def test_min_level(self):
        records = [rec("debug"), rec("warning"), rec("error"), rec(None)]
        out = list(stage_min_level("warning")(iter(records)))
        assert [r.level for r in out] == ["warning", "error"]

    def test_sample_every(self):
        records = [rec(msg=str(i)) for i in range(10)]
        out = list(stage_sample_every(3)(iter(records)))
        assert [r.message for r in out] == ["0", "3", "6", "9"]


class TestStatsStage:
    def test_counts(self):
        stats = PipelineStats()
        records = [rec("error"), rec("error"), rec("info")]
        out = list(stage_stats(stats)(iter(records)))
        assert len(out) == 3
        assert stats.seen == 3
        assert stats.by_level == {"error": 2, "info": 1}

    def test_stats_in_pipeline(self):
        stats = PipelineStats()
        pipeline = Pipeline().then(stage_stats(stats)).then(stage_limit(1))
        pipeline.run([rec("debug"), rec("info")])
        assert stats.seen == 2
