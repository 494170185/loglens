"""M21 — request classification."""

from __future__ import annotations

from loglens.classify import (
    category_counts,
    classify_method,
    classify_path,
    classify_request,
    mime_of,
    slowest_categories,
)
from loglens.model import Record


def rec(fields):
    return Record(raw="", message="", fields=fields)


class TestClassifyPath:
    def test_api(self):
        assert classify_path("/api/v1/users") == "api"
        assert classify_path("/v2/orders") == "api"

    def test_static_assets(self):
        assert classify_path("/static/app.css") == "static"
        assert classify_path("/logo.png") == "static"
        assert classify_path("/app.js?v=3") == "static"

    def test_auth(self):
        assert classify_path("/login") == "auth"
        assert classify_path("/api/oauth/token") == "api"  # api wins first

    def test_health(self):
        assert classify_path("/health") == "health"
        assert classify_path("/healthz") == "health"
        assert classify_path("/api/status") == "api"  # api first

    def test_admin(self):
        assert classify_path("/admin/users") == "admin"

    def test_webhook(self):
        assert classify_path("/hooks/github") == "webhook"

    def test_other(self):
        assert classify_path("/about") == "other"

    def test_empty(self):
        assert classify_path(None) == "other"
        assert classify_path("") == "other"


class TestClassifyMethod:
    def test_read_write_meta(self):
        assert classify_method("GET") == "read"
        assert classify_method("HEAD") == "read"
        assert classify_method("POST") == "write"
        assert classify_method("DELETE") == "write"
        assert classify_method("OPTIONS") == "meta"

    def test_case_insensitive(self):
        assert classify_method("get") == "read"

    def test_unknown(self):
        assert classify_method("BREW") == "unknown"
        assert classify_method(None) == "unknown"


class TestMime:
    def test_common_extensions(self):
        assert mime_of("/a/b.html") == "text/html"
        assert mime_of("/a/b.js") == "application/javascript"
        assert mime_of("/img/x.PNG") == "image/png"
        assert mime_of("/font.woff2") == "font/woff2"

    def test_query_string_stripped(self):
        assert mime_of("/data.json?callback=x") == "application/json"

    def test_unknown(self):
        assert mime_of("/no/ext") == "unknown"
        assert mime_of(None) == "unknown"


class TestClassifyRequest:
    def test_bundle(self):
        result = classify_request(rec({"path": "/api/users", "method": "GET"}))
        assert result["category"] == "api"
        assert result["verb_group"] == "read"
        assert result["mime"] == "unknown"

    def test_static_bundle(self):
        result = classify_request(rec({"path": "/x/y.svg", "method": "POST"}))
        assert result["category"] == "static"
        assert result["verb_group"] == "write"
        assert result["mime"] == "image/svg+xml"


class TestCategoryCounts:
    def test_tally(self):
        records = [
            rec({"path": "/api/a"}),
            rec({"path": "/api/b"}),
            rec({"path": "/login"}),
        ]
        counts = category_counts(records)
        assert counts["api"] == 2
        assert counts["auth"] == 1


class TestSlowestCategories:
    def test_ranked_by_mean(self):
        records = [
            rec({"path": "/api/a", "dur": 100}),
            rec({"path": "/api/b", "dur": 200}),
            rec({"path": "/login", "dur": 10}),
        ]
        ranked = slowest_categories(records)
        assert ranked[0][0] == "api"
        assert ranked[0][1] == 150.0

    def test_top_limit(self):
        records = [rec({"path": "/api/a", "dur": i}) for i in range(10)]
        assert len(slowest_categories(records, top=1)) == 1
