"""M42d — format checker: audit a log file's structural consistency."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from loglens.model import Record

KNOWN_FORMATS = ("json", "access", "syslog", "logfmt", "plain", "raw")


@dataclass
class FormatReport:
    """Consistency audit of one record stream."""

    total: int = 0
    with_timestamp: int = 0
    with_level: int = 0
    format_votes: Counter = field(default_factory=Counter)

    @property
    def timestamp_coverage(self) -> float:
        return self.with_timestamp / self.total if self.total else 0.0

    @property
    def level_coverage(self) -> float:
        return self.with_level / self.total if self.total else 0.0

    @property
    def dominant_format(self) -> str:
        if not self.format_votes:
            return "raw"
        return self.format_votes.most_common(1)[0][0]


def per_line_format(line: str) -> str:
    """Which parser would claim this single line."""
    from loglens.parsers.access import looks_like_access
    from loglens.parsers.jsonl import looks_like_json
    from loglens.parsers.logfmt import looks_like_logfmt
    from loglens.parsers.syslog import looks_like_syslog

    if looks_like_json(line):
        return "json"
    if looks_like_access(line):
        return "access"
    if looks_like_syslog(line):
        return "syslog"
    if looks_like_logfmt(line) and "=" in line:
        return "logfmt"
    from loglens.parsers.detect import parse_plain_line

    if parse_plain_line(line) is not None:
        return "plain"
    return "raw"


def audit_format(records: Iterable[Record]) -> FormatReport:
    """Coverage stats and per-line format votes."""
    report = FormatReport()
    for rec in records:
        report.total += 1
        if rec.timestamp is not None:
            report.with_timestamp += 1
        if rec.level is not None:
            report.with_level += 1
        report.format_votes[per_line_format(rec.raw)] += 1
    return report


@dataclass
class ConsistencyIssue:
    kind: str
    detail: str
    count: int


def consistency_issues(report: FormatReport) -> list[ConsistencyIssue]:
    """Human-readable problems found by an audit."""
    issues: list[ConsistencyIssue] = []
    if report.total == 0:
        issues.append(ConsistencyIssue("empty", "no records at all", 0))
        return issues
    mixed = [
        f
        for f, c in report.format_votes.items()
        if c > report.total * 0.2 and f != report.dominant_format
    ]
    if mixed:
        issues.append(
            ConsistencyIssue(
                "mixed-format",
                f"dominant {report.dominant_format}, also {', '.join(sorted(mixed))}",
                sum(report.format_votes[f] for f in mixed),
            )
        )
    if report.timestamp_coverage < 0.9:
        issues.append(
            ConsistencyIssue(
                "missing-timestamps",
                f"only {report.timestamp_coverage:.0%} carry timestamps",
                report.total - report.with_timestamp,
            )
        )
    if report.level_coverage < 0.5 and report.dominant_format not in ("access",):
        issues.append(
            ConsistencyIssue(
                "missing-levels",
                f"only {report.level_coverage:.0%} carry severity levels",
                report.total - report.with_level,
            )
        )
    return issues
