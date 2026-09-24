"""M25 — URL breakdown."""

from __future__ import annotations

from loglens.urls import (
    break_down_url,
    enrich_record_with_url,
    normalize_path,
    path_segments,
    route_shape,
)


class TestBreakDown:
    def test_full_url(self):
        fields = break_down_url("https://api.example.com/v1/users?page=2&sort=name")
        assert fields["scheme"] == "https"
        assert fields["host"] == "api.example.com"
        assert fields["path"] == "/v1/users"
        assert fields["query_params"] == {"page": "2", "sort": "name"}
        assert fields["q_page"] == "2"

    def test_plain_path_only(self):
        fields = break_down_url("/api/health")
        assert fields["path"] == "/api/health"
        assert "host" not in fields
        assert "query_params" not in fields

    def test_fragment(self):
        fields = break_down_url("http://x.io/a#section2")
        assert fields["fragment"] == "section2"

    def test_repeated_param_keeps_last(self):
        fields = break_down_url("/x?a=1&a=2")
        assert fields["q_a"] == "2"

    def test_blank_value_kept(self):
        fields = break_down_url("/x?flag=")
        assert fields["q_flag"] == ""

    def test_bare_slash_path(self):
        fields = break_down_url("http://h")
        assert fields["path"] == "/"


class TestSegments:
    def test_segments(self):
        assert path_segments("/a/b/c") == ["a", "b", "c"]

    def test_empty(self):
        assert path_segments("/") == []

    def test_double_slash_collapsed(self):
        assert path_segments("/a//b") == ["a", "b"]


class TestRouteShape:
    def test_numeric_ids_collapsed(self):
        assert route_shape("/api/users/42/orders/7") == "/api/users/:id/orders/:id"

    def test_hex_segment_becomes_hash(self):
        assert route_shape("/files/deadbeefcafebabe") == "/files/:hash"

    def test_names_kept(self):
        assert route_shape("/api/users/list") == "/api/users/list"

    def test_root(self):
        assert route_shape("/") == "/"


class TestNormalizePath:
    def test_query_stripped(self):
        assert normalize_path("/users/3?page=2") == "/users/:id"

    def test_trailing_slash_removed(self):
        assert normalize_path("/api/health/") == "/api/health"


class TestEnrichRecord:
    def test_path_enriched(self):
        fields = {"path": "/api/users/3?page=1"}
        out = enrich_record_with_url(fields)
        assert out["q_page"] == "1"
        assert out["path"] == "/api/users/3"

    def test_url_key_fallback(self):
        out = enrich_record_with_url({"url": "http://h/a"})
        assert out["host"] == "h"

    def test_no_url_untouched(self):
        fields = {"a": 1}
        assert enrich_record_with_url(fields) == fields
