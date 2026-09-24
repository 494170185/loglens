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
            level = paint_level(rec.level, enabled=use_color)
            prefix = f"{level or '-':<8}" if use_color else f"{(rec.level or '-'):<8}"
            print(f"{prefix} {rec.message or rec.raw}")
            if use_color and rec.level:
                pass  # color already applied through paint_level
    else:
        print(write_records(records, args.format))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = globals().get(f"cmd_{args.command}")
    if handler is None:
        parser.error(f"no handler for command {args.command!r}")
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
