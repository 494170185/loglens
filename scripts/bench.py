"""Bench: generate a synthetic log and time the pipeline end to end.

Usage:
    python scripts/bench.py [--lines N] [--out PATH]

Writes a mixed-format synthetic log, runs the collector over it, and
prints timings per stage. Used to watch for performance regressions.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loglens.collect import Collector
from loglens.filters.builtin import compile_query, record_context
from loglens.rankings import top_groups


def synthetic_line(i: int) -> str:
    if i % 3 == 0:
        return (
            f'10.0.0.{i % 250} - - [19/Sep/2026:10:{(i // 60) % 60:02d}:{i % 60:02d} +0000] '
            f'"GET /api/item/{i % 500} HTTP/1.1" {200 + (i % 5 == 0) * 300} {i % 900}'
        )
    if i % 3 == 1:
        return (
            f"2026-09-19 10:{(i // 60) % 60:02d}:{i % 60:02d} "
            f"{'ERROR' if i % 17 == 0 else 'INFO'} worker-{i % 8} handled request in {i % 300}ms"
        )
    ts = f"2026-09-19T10:{(i // 60) % 60:02d}:{i % 60:02d}Z"
    return f'{{"ts": "{ts}", "level": "info", "msg": "job {i % 200} done"}}'


def generate(path: Path, lines: int) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for i in range(lines):
            handle.write(synthetic_line(i) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", type=int, default=50_000)
    parser.add_argument("--out", default="bench-results/sample.log")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    generate(out, args.lines)
    gen_seconds = time.perf_counter() - started

    started = time.perf_counter()
    collector = Collector()
    records = collector.collect_file(out)
    parse_seconds = time.perf_counter() - started

    started = time.perf_counter()
    flt = compile_query("level = error or status >= 500")
    matched = [r for r in records if flt.matches(record_context(r))]
    filter_seconds = time.perf_counter() - started

    started = time.perf_counter()
    top_groups(records, "client", n=10)
    agg_seconds = time.perf_counter() - started

    print(f"lines generated : {args.lines:,} ({gen_seconds:.2f}s)")
    print(f"records parsed  : {len(records):,} ({parse_seconds:.2f}s)")
    print(f"filter matches  : {len(matched):,} ({filter_seconds:.2f}s)")
    print(f"top-n grouping  : {agg_seconds:.2f}s")
    print(f"throughput      : {len(records) / max(parse_seconds, 1e-9):,.0f} records/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
