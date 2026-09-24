"""M41 — doctor: environment and self-integrity checks."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from loglens import __version__


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str

    def line(self) -> str:
        status = "ok" if self.ok else "FAIL"
        return f"[{status:>4}] {self.name}: {self.detail}"


def check_python() -> CheckResult:
    version = sys.version_info
    ok = version >= (3, 12)
    return CheckResult(
        "python",
        ok,
        f"{version.major}.{version.minor}.{version.micro}"
        + ("" if ok else " (3.12+ required)"),
    )


def check_parsers() -> CheckResult:
    from loglens.parsers.access import parse_access_line
    from loglens.parsers.jsonl import parse_json_line
    from loglens.parsers.logfmt import parse_logfmt_line
    from loglens.parsers.syslog import parse_syslog_line

    line = '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10'
    assert parse_access_line(line).fields.get("status") == 200
    assert parse_json_line('{"msg": "x"}').message == "x"
    assert parse_logfmt_line("a=1").fields.get("a") == 1
    assert parse_syslog_line("Sep 19 10:07:21 h app: m") is not None
    return CheckResult("parsers", True, "access/jsonl/logfmt/syslog all parse")


def check_filter_language() -> CheckResult:
    from loglens.filters.builtin import compile_query

    flt = compile_query("level:error+ and status >= 500")
    hit = flt.matches({"level": "error", "status": 503, "message": "", "raw": ""})
    miss = flt.matches({"level": "info", "status": 200, "message": "", "raw": ""})
    if hit and not miss:
        return CheckResult("filter-language", True, "expression engine works")
    return CheckResult("filter-language", False, "expression semantics broken")


def check_table_rendering() -> CheckResult:
    from loglens.tables import render_table

    text = render_table([("a", 1)], headers=("h1", "h2"))
    rows = [ln for ln in text.split("\n") if "|" in ln]
    widths = {len(ln.split("|")[0]) for ln in rows}
    if len(rows) == 2 and len(widths) == 1:
        return CheckResult("tables", True, "alignment engine works")
    return CheckResult("tables", False, f"unexpected table output: {text!r}")


def check_profiles() -> CheckResult:
    from loglens.profiles import BUILTIN_PROFILES

    names = ", ".join(sorted(BUILTIN_PROFILES))
    return CheckResult("profiles", True, f"builtins: {names}")


def check_packaging() -> CheckResult:
    modules = [
        "loglens.cli",
        "loglens.collect",
        "loglens.pipeline",
        "loglens.report",
        "loglens.writers",
    ]
    missing = []
    for name in modules:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        return CheckResult("modules", False, f"missing: {', '.join(missing)}")
    return CheckResult("modules", True, f"{len(modules)} core modules importable")


def run_all() -> list[CheckResult]:
    return [
        check_modules_first(),
        check_python(),
        check_parsers(),
        check_filter_language(),
        check_table_rendering(),
        check_profiles(),
        check_packaging(),
    ]


def check_modules_first() -> CheckResult:
    return CheckResult("version", True, f"loglens {__version__}")


def render_report(results: list[CheckResult]) -> str:
    lines = [f"loglens {__version__} doctor", ""]
    lines += [r.line() for r in results]
    failures = [r for r in results if not r.ok]
    lines.append("")
    if failures:
        lines.append(f"{len(failures)} check(s) failed")
    else:
        lines.append("all checks passed")
    return "\n".join(lines)


def cmd_doctor(_args) -> int:
    results = run_all()
    print(render_report(results))
    return 0 if all(r.ok for r in results) else 1
