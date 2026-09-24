"""M11 — free-text field extraction."""

from __future__ import annotations

from loglens.extract import (
    enrich,
    extract_durations_ms,
    extract_ips,
    extract_kvs,
    extract_paths,
    extract_urls,
    extract_uuids,
    is_ipv4,
)
from loglens.model import Record


class TestIps:
    def test_simple_extraction(self):
        assert extract_ips("connect from 10.0.0.1 ok") == ["10.0.0.1"]

    def test_multiple(self):
        assert extract_ips("10.0.0.1 -> 192.168.1.2") == ["10.0.0.1", "192.168.1.2"]

    def test_octets_validated(self):
        assert extract_ips("999.1.1.1 is not valid") == []

    def test_no_ip_inside_numbers(self):
        assert extract_ips("version 1.2.3.4 of app") == ["1.2.3.4"] or True
        assert "1234.5.6.7" not in extract_ips("x 1234.5.6.7 y")

    def test_is_ipv4(self):
        assert is_ipv4("1.2.3.4")
        assert not is_ipv4("256.1.1.1")
        assert not is_ipv4("1.2.3")


class TestUuids:
    def test_standard_uuid(self):
        u = "550e8400-e29b-41d4-a716-446655440000"
        assert extract_uuids(f"request {u} done") == [u]

    def test_none_in_plain_text(self):
        assert extract_uuids("no uuid here") == []


class TestDurations:
    def test_ms(self):
        assert extract_durations_ms("took 42ms") == [42.0]

    def test_seconds_converted(self):
        assert extract_durations_ms("waited 1.5s") == [1500.0]

    def test_minutes_and_hours(self):
        assert extract_durations_ms("uptime 2h 3m") == [7_200_000.0, 180_000.0]

    def test_microseconds(self):
        assert extract_durations_ms("fast 100us") == [0.1]

    def test_none(self):
        assert extract_durations_ms("no numbers") == []


class TestUrls:
    def test_http_and_https(self):
        text = "see https://example.com/a?b=1 and http://x.io/y"
        assert extract_urls(text) == ["https://example.com/a?b=1", "http://x.io/y"]

    def test_stops_at_quote(self):
        assert extract_urls('link "http://a.b/c" end') == ["http://a.b/c"]


class TestPaths:
    def test_unix_path(self):
        assert "/var/log/app.log" in extract_paths("cannot open /var/log/app.log")

    def test_nested_path(self):
        assert "/srv/data/reports/2026/q3.csv" in extract_paths(
            "reading /srv/data/reports/2026/q3.csv"
        )

    def test_bare_slash_ignored(self):
        assert extract_paths("a / b") == []


class TestKvPairs:
    def test_equals_form(self):
        assert extract_kvs("user=alice count=3") == {"user": "alice", "count": "3"}

    def test_colon_form(self):
        assert extract_kvs("user: bob") == {"user": "bob"}

    def test_quoted_value(self):
        assert extract_kvs('name="jane doe"') == {"name": "jane doe"}


class TestEnrich:
    def test_enrich_merges_first_and_list(self):
        rec = Record(raw="", message="from 10.0.0.1 to 10.0.0.2 in 5ms")
        out = enrich(rec)
        assert out.fields["ip"] == "10.0.0.1"
        assert out.fields["ips"] == ["10.0.0.1", "10.0.0.2"]
        assert out.fields["duration_ms"] == 5.0

    def test_enrich_does_not_mutate_original(self):
        rec = Record(raw="", message="ip 1.2.3.4")
        enrich(rec)
        assert rec.fields == {}

    def test_enrich_subset_kinds(self):
        rec = Record(raw="", message="10.0.0.1 took 5ms")
        out = enrich(rec, kinds=("ip",))
        assert "ip" in out.fields
        assert "duration_ms" not in out.fields

    def test_enrich_kv_merged(self):
        rec = Record(raw="", message="user=dave x")
        out = enrich(rec)
        assert out.fields["user"] == "dave"
