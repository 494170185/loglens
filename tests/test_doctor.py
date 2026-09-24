"""M41 — doctor self-checks."""

from __future__ import annotations

from loglens.cli import main
from loglens.doctor import (
    check_filter_language,
    check_parsers,
    check_python,
    render_report,
    run_all,
)


class TestIndividualChecks:
    def test_python_check(self):
        result = check_python()
        assert result.name == "python"
        assert result.ok  # CI runs on 3.12+

    def test_parsers_check(self):
        assert check_parsers().ok

    def test_filter_language_check(self):
        assert check_filter_language().ok

    def test_version_line(self):
        results = run_all()
        assert results[0].name == "version"
        assert "loglens" in results[0].detail


class TestReport:
    def test_all_checks_present(self):
        results = run_all()
        names = [r.name for r in results]
        assert {"python", "parsers", "filter-language", "tables", "profiles"} <= set(names)

    def test_render_report_all_ok(self):
        text = render_report(run_all())
        assert "all checks passed" in text
        assert "doctor" in text

    def test_render_report_with_failure(self):
        from loglens.doctor import CheckResult

        text = render_report(
            [CheckResult("broken", False, "synthetic failure")]
        )
        assert "FAIL" in text
        assert "1 check(s) failed" in text


class TestCliIntegration:
    def test_doctor_command(self, capsys):
        code = main(["doctor"])
        out = capsys.readouterr().out
        assert code == 0
        assert "all checks passed" in out
