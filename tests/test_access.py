"""M5 — combined access-log parsing."""

from __future__ import annotations

import pytest

from loglens.parsers.access import looks_like_access, parse_access_line, status_class


class TestParseCombined:
    def test_full_combined_line(self, nginx_line):
        rec = parse_access_line(nginx_line)
        assert rec.fields["client"] == "172.17.0.1"
        assert rec.fields["method"] == "GET"
        assert rec.fields["path"] == "/api/health"
        assert rec.fields["status"] == 200
        assert rec.fields["bytes"] == 12
        assert rec.fields["agent"] == "curl/8.5.0"
        assert rec.message == "GET /api/health -> 200"

    def test_common_format_without_referer_agent(self):
        line = '10.0.0.5 - - [19/Sep/2026:10:07:21 +0000] "POST /login HTTP/1.1" 302 -'
        rec = parse_access_line(line)
        assert rec.fields["status"] == 302
        assert rec.fields["bytes"] == 0
        assert "referer" not in rec.fields
        assert "agent" not in rec.fields

    def test_dash_bytes_becomes_zero(self):
        line = '10.0.0.5 - - [19/Sep/2026:10:07:21 +0000] "GET /x HTTP/1.1" 404 -'
        rec = parse_access_line(line)
        assert rec.fields["bytes"] == 0

    def test_source_and_line_no_round_trip(self):
        rec = parse_access_line(
            '10.0.0.5 - - [19/Sep/2026:10:07:21 +0000] "GET /x HTTP/1.1" 200 5',
            source="access.log",
            line_no=12,
        )
        assert rec.source == "access.log"
        assert rec.line_no == 12

    def test_ident_and_user_captured(self):
        line = (
            '10.0.0.5 ident bob [19/Sep/2026:10:07:21 +0000] '
            '"GET /x HTTP/1.1" 200 5'
        )
        rec = parse_access_line(line)
        assert rec.fields["ident"] == "ident"
        assert rec.fields["user"] == "bob"

    def test_path_with_query_string(self):
        line = (
            '10.0.0.5 - - [19/Sep/2026:10:07:21 +0000] '
            '"GET /search?q=logs HTTP/1.1" 200 5'
        )
        rec = parse_access_line(line)
        assert rec.fields["path"] == "/search?q=logs"


class TestFallbacks:
    def test_garbage_line_falls_back_to_raw(self):
        rec = parse_access_line("totally not a log line")
        assert rec.fields == {}
        assert rec.message == "totally not a log line"

    def test_empty_line(self):
        rec = parse_access_line("")
        assert rec.fields == {}


class TestHeuristics:
    @pytest.mark.parametrize(
        "line",
        [
            '1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10',
            '1.2.3.4 - alice [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 10',
        ],
    )
    def test_recognized(self, line):
        assert looks_like_access(line)

    @pytest.mark.parametrize(
        "line",
        ["2026-09-19 10:07:21 INFO starting up", "hello world", ""],
    )
    def test_not_recognized(self, line):
        assert not looks_like_access(line)


class TestStatusClass:
    @pytest.mark.parametrize(
        ("status", "label"),
        [
            (200, "2xx"),
            (204, "2xx"),
            (301, "3xx"),
            (302, "3xx"),
            (401, "4xx"),
            (404, "4xx"),
            (418, "4xx"),
            (500, "5xx"),
            (503, "5xx"),
        ],
    )
    def test_classes(self, status, label):
        assert status_class(status) == label
