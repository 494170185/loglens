"""M36 — CLI entry point and the cat command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from loglens import __version__
from loglens.ansi import colors_enabled, paint_level
from loglens.collect import Collector
from loglens.filters.builtin import compile_query, record_context
from loglens.sources import normalize_paths
from loglens.writers import write_records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loglens",
        description="Slice through server logs from the terminal.",
    )
    parser.add_argument("--version", action="version", version=f"loglens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    cat = sub.add_parser("cat", help="print parsed records")
    _add_input_args(cat)
    cat.add_argument("-f", "--format", choices=["text", "json", "jsonl", "csv"], default="text")
    cat.add_argument("-n", "--limit", type=int, default=None)
    cat.add_argument("--no-stitch", action="store_true", help="disable multiline folding")
    cat.add_argument("--no-enrich", action="store_true", help="disable field extraction")
    _add_query_arg(cat)

    for name, help_text in [
        ("stats", "count/level breakdown overview"),
        ("filter", "apply a query and print matches (alias of cat -q)"),
    ]:
        p = sub.add_parser(name, help=help_text)
        _add_input_args(p)
        _add_query_arg(p)

    grep = sub.add_parser("grep", help="quick substring search")
    _add_input_args(grep)
    grep.add_argument("needle")
    grep.add_argument("-i", "--ignore-case", action="store_true")
    grep.add_argument("-v", "--invert", action="store_true")

    top = sub.add_parser("top", help="top-N groups by a field")
    _add_input_args(top)
    top.add_argument("field")
    top.add_argument("-n", type=int, default=10)
    top.add_argument("--by", default="count", help="count | avg:FIELD | sum:FIELD | max:FIELD")

    hist = sub.add_parser("hist", help="histogram of a numeric field")
    _add_input_args(hist)
    hist.add_argument("field")
    hist.add_argument("--bins", type=int, default=20)

    timeline = sub.add_parser("timeline", help="events per time bucket")
    _add_input_args(timeline)
    timeline.add_argument("--bucket", default="1m", dest="bucket_size")
    timeline.add_argument("--errors", action="store_true", help="show 5xx fraction series")

    report = sub.add_parser("report", help="markdown summary report")
    _add_input_args(report)
    report.add_argument("-o", "--output", default=None, help="write to file")

    bursts = sub.add_parser("bursts", help="detect repeated message bursts")
    _add_input_args(bursts)
    bursts.add_argument("--min-repeat", type=int, default=5)

    anomalies = sub.add_parser("anomalies", help="z-score outliers on a field")
    _add_input_args(anomalies)
    anomalies.add_argument("field")
    anomalies.add_argument("--min-z", type=float, default=3.0)

    silences = sub.add_parser("silences", help="detect quiet gaps")
    _add_input_args(silences)
    silences.add_argument("--min-seconds", type=float, default=300.0)

    sessions = sub.add_parser("sessions", help="group records into sessions")
    _add_input_args(sessions)
    sessions.add_argument("--key", default="client")
    sessions.add_argument("--timeout-minutes", type=float, default=30.0)

    watch = sub.add_parser("watch", help="follow a file and print new records")
    watch.add_argument("files", nargs="+")
    watch.add_argument("-q", "--query", default=None)

    classify_cmd = sub.add_parser("classify", help="request category breakdown")
    _add_input_args(classify_cmd)

    sub.add_parser("doctor", help="environment self-check")

    return parser


def _add_input_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("files", nargs="*", help="log files, dirs or glob patterns")
    p.add_argument("--format-hint", default=None, dest="fmt",
                   choices=["json", "access", "syslog", "logfmt", "plain", "raw"])


def _add_query_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("-q", "--query", default=None,
                   help="filter expression, e.g. 'level:error+ and status >= 500'")


def resolve_files(files: Sequence[str]) -> list[str]:
    """Expand patterns; stdin marker '-' stays for caller handling."""
    if not files or list(files) == ["-"]:
        return []
    return [str(p) for p in normalize_paths(list(files))]


def load_records(args) -> list:
    """Collect records per the common input arguments."""
    paths = resolve_files(args.files)
    collector = Collector()
    all_records = []
    for path in paths:
        all_records.extend(collector.collect_file(path, fmt=getattr(args, "fmt", None)))
    if not paths and sys.stdin.isatty() is False:
        import sys as _sys

        data = _sys.stdin.read()
        if data:
            all_records = collector.collect_lines(data.splitlines())
    if getattr(args, "query", None):
        flt = compile_query(args.query)
        all_records = [r for r in all_records if flt.matches(record_context(r))]
    return all_records


def cmd_cat(args) -> int:
    collector = Collector(
        stitch=not args.no_stitch, enrich=not args.no_enrich
    )
    paths = resolve_files(args.files)
    records = []
    for path in paths:
        records.extend(collector.collect_file(path, fmt=args.fmt))
    if args.query:
        flt = compile_query(args.query)
        records = [r for r in records if flt.matches(record_context(r))]
    if args.limit is not None:
        records = records[: args.limit]
    use_color = colors_enabled(stream_is_tty=sys.stdout.isatty())
    if args.format == "text":
        for rec in records:
            label = rec.level or "-"
            if use_color:
                label = paint_level(rec.level, enabled=True) or "-"
            print(f"{label:<8} {rec.message or rec.raw}")
    else:
        print(write_records(records, args.format))
    return 0


def cmd_stats(args) -> int:
    records = load_records(args)
    from loglens.aggregate import group_by
    from loglens.tables import render_key_value, render_table

    pairs: list[tuple[str, str]] = [("records", str(len(records)))]
    level_groups = group_by(records, "level")
    counted = {g.key: g.count for g in level_groups if g.key != "(missing)"}
    if counted:
        pairs.append(
            ("levels", ", ".join(f"{k}:{v}" for k, v in sorted(counted.items())))
        )
    status_total = sum(1 for r in records if r.get("status") is not None)
    if status_total:
        from loglens.metrics import status_breakdown

        bd = status_breakdown(records)
        pairs.append(("status errors", f"{bd.error_rate():.1%}"))
    print(render_key_value(pairs))
    if counted:
        rows = [(k, v) for k, v in sorted(counted.items(), key=lambda kv: -kv[1])]
        print()
        print(render_table(rows, headers=("level", "count")))
    return 0


def cmd_filter(args) -> int:
    """Alias of `cat -q` with text output."""
    records = load_records(args)
    use_color = colors_enabled(stream_is_tty=sys.stdout.isatty())
    for rec in records:
        label = rec.level or "-"
        if use_color:
            label = paint_level(rec.level, enabled=True) or "-"
        print(f"{label:<8} {rec.message or rec.raw}")
    return 0


def cmd_grep(args) -> int:
    records = load_records(args)
    needle = args.needle.lower() if args.ignore_case else args.needle
    for rec in records:
        haystack = (rec.message + "\n" + rec.raw).lower() if args.ignore_case else (
            rec.message + "\n" + rec.raw
        )
        hit = needle in haystack
        if hit != args.invert:
            print(rec.raw)
    return 0


def cmd_top(args) -> int:
    records = load_records(args)
    from loglens.rankings import top_groups
    from loglens.tables import render_table

    groups = top_groups(records, args.field, n=args.n, by=args.by)
    rows = [(g.key, g.count) for g in groups]
    print(render_table(rows, headers=(args.field, "count")))
    return 0


def cmd_hist(args) -> int:
    records = load_records(args)
    from loglens.rankings import field_histogram

    lines = field_histogram(records, args.field, bins=args.bins)
    for line in lines:
        print(line)
    if not lines:
        print("(no values)")
    return 0


def cmd_timeline(args) -> int:
    records = load_records(args)
    from loglens.tables import render_table
    from loglens.timebuckets import bucket_counts, error_rate_series

    if args.errors:
        series = error_rate_series(records, args.bucket_size)
        rows = [(start.strftime("%H:%M"), f"{rate:.1%}") for start, rate in series]
        print(render_table(rows, headers=("bucket", "5xx fraction")))
    else:
        series = bucket_counts(records, args.bucket_size)
        rows = [(start.strftime("%H:%M"), count) for start, count in series]
        print(render_table(rows, headers=("bucket", "events")))
    return 0


def cmd_report(args) -> int:
    records = load_records(args)
    from loglens.report import build_summary_report

    text = build_summary_report(records)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(text, encoding="utf-8")
        print(f"report written to {args.output}")
    else:
        print(text)
    return 0


def cmd_bursts(args) -> int:
    records = load_records(args)
    from loglens.bursts import detect_bursts
    from loglens.tables import render_table

    bursts = detect_bursts(records, min_repeat=args.min_repeat)
    rows = [(b.count, b.example[:60], str(b.first_line or "")) for b in bursts]
    print(render_table(rows, headers=("count", "example", "line")))
    return 0


def cmd_anomalies(args) -> int:
    records = load_records(args)
    from loglens.anomalies import detect_anomalies
    from loglens.tables import render_table

    anomalies = detect_anomalies(records, args.field, min_z=args.min_z)
    rows = [
        (a.zscore, a.value, f"mean={a.mean:.1f}", (a.record.message or a.record.raw)[:40])
        for a in anomalies
    ]
    print(render_table(rows, headers=("z", "value", "vs", "record")))
    return 0


def cmd_silences(args) -> int:
    records = load_records(args)
    from loglens.anomalies import detect_silences
    from loglens.tables import render_table

    silences = detect_silences(records, min_seconds=args.min_seconds)
    rows = [
        (s.start.strftime("%H:%M:%S"), s.end.strftime("%H:%M:%S"), f"{s.minutes:.0f}m")
        for s in silences
    ]
    print(render_table(rows, headers=("from", "to", "gap")))
    return 0


def cmd_sessions(args) -> int:
    records = load_records(args)
    from datetime import timedelta as _td

    from loglens.sessions import sessionize
    from loglens.tables import render_table

    sessions = sessionize(
        records, key_field=args.key, idle_timeout=_td(minutes=args.timeout_minutes)
    )
    rows = [(s.key, s.count, s.summary_line().split(": ", 1)[-1]) for s in sessions]
    print(render_table(rows, headers=(args.key, "events", "window")))
    return 0


def cmd_watch(args) -> int:
    from loglens.watch import FileFollower

    flt = compile_query(args.query) if args.query else None
    followers = [FileFollower(path) for path in args.files]

    def on_lines(lines):
        from loglens.parsers.detect import parse_with

        for _no, line in lines:
            rec = parse_with("raw", line)
            if flt is None or flt.matches(record_context(rec)):
                print(rec.raw)

    try:
        # follow the first file only: multiple simultaneous tails need
        # a selector loop left to a future milestone
        followers[0].follow(on_lines)
    except KeyboardInterrupt:
        print()
    return 0


def cmd_classify(args) -> int:
    records = load_records(args)
    from loglens.classify import category_counts
    from loglens.tables import render_table

    counts = category_counts(records)
    rows = [(name, count) for name, count in counts.most_common()]
    print(render_table(rows, headers=("category", "requests")))
    return 0


def cmd_doctor(args) -> int:
    from loglens.doctor import render_report, run_all

    results = run_all()
    print(render_report(results))
    return 0 if all(r.ok for r in results) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = globals().get(f"cmd_{args.command}")
    if handler is None:
        parser.error(f"no handler for command {args.command!r}")
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
