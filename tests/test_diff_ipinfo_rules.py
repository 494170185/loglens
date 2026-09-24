"""M42c — tests for diff, ipinfo and rules."""

from __future__ import annotations

from loglens.diff import diff_records, field_diff, message_counts
from loglens.ipinfo import classify_ip, ip_scope_counts, public_clients
from loglens.model import Record
from loglens.rules import (
    RulePack,
    all_of,
    any_of,
    default_pack,
    field_above,
    field_below,
    field_equals,
    message_contains,
)


def rec(fields, msg=""):
    return Record(raw=msg, message=msg, fields=fields)


class TestDiff:
    def test_identical_streams_no_changes(self):
        a = [rec({}, "same error")]
        b = [rec({}, "same error")]
        report = diff_records(a, b)
        assert not report.has_changes

    def test_new_message_detected(self):
        before = [rec({}, "old")]
        after = [rec({}, "old"), rec({}, "fresh failure")]
        report = diff_records(before, after)
        assert "fresh failure" in report.only_after

    def test_disappeared_message(self):
        before = [rec({}, "transient issue")]
        after = [rec({}, "other")]
        report = diff_records(before, after)
        assert "transient issue" in report.only_before

    def test_count_change_tracked(self):
        before = [rec({}, "warn")] * 2
        after = [rec({}, "warn")] * 5
        report = diff_records(before, after)
        assert ("warn", 2, 5) in report.count_changes

    def test_normalization_applies(self):
        before = [rec({}, "timeout after 5ms")]
        after = [rec({}, "timeout after 9ms")]
        assert not diff_records(before, after).has_changes

    def test_message_counts(self):
        counts = message_counts([rec({}, "a"), rec({}, "a"), rec({}, "b")])
        assert counts == {"a": 2, "b": 1}

    def test_field_diff_detects_drift(self):
        before = [rec({"version": "1.0"})]
        after = [rec({"version": "1.1"})]
        out = field_diff(before, after, "version")
        assert out == {"version": ("1.0", "1.1")}

    def test_field_diff_same_value(self):
        assert field_diff([rec({"v": 1})], [rec({"v": 1})], "v") == {}


class TestIpInfo:
    def test_private_ranges(self):
        assert classify_ip("10.0.0.1").scope == "private"
        assert classify_ip("192.168.1.1").scope == "private"
        assert classify_ip("172.16.0.1").scope == "private"
        assert classify_ip("172.31.255.255").scope == "private"

    def test_public(self):
        assert classify_ip("8.8.8.8").scope == "public"
        assert classify_ip("8.8.8.8").is_public

    def test_loopback_linklocal(self):
        assert classify_ip("127.0.0.1").scope == "loopback"
        assert classify_ip("169.254.1.1").scope == "link-local"

    def test_cgnat(self):
        assert classify_ip("100.64.0.1").scope == "cgnat"
        assert classify_ip("100.127.255.255").scope == "cgnat"
        assert classify_ip("100.128.0.1").scope == "public"

    def test_172_edge(self):
        assert classify_ip("172.15.0.1").scope == "public"
        assert classify_ip("172.32.0.1").scope == "public"

    def test_invalid(self):
        assert classify_ip("999.1.1.1").scope == "invalid"
        assert classify_ip("not-an-ip").scope == "invalid"

    def test_scope_counts(self):
        records = [rec({"client": "10.0.0.1"}), rec({"client": "8.8.8.8"})]
        counts = ip_scope_counts(records)
        assert counts == {"private": 1, "public": 1}

    def test_public_clients_distinct(self):
        records = [
            rec({"client": "8.8.8.8"}),
            rec({"client": "8.8.8.8"}),
            rec({"client": "10.0.0.1"}),
        ]
        assert public_clients(records) == ["8.8.8.8"]


class TestRules:
    def test_field_predicates(self):
        assert field_equals("status", 500)(rec({"status": 500}))
        assert not field_equals("status", 500)(rec({"status": 200}))
        assert field_above("dur", 100)(rec({"dur": 200}))
        assert field_below("dur", 100)(rec({"dur": 50}))
        assert not field_above("dur", 100)(rec({"dur": "slow"}))

    def test_message_contains(self):
        assert message_contains("memory")(rec({}, "Out of Memory!"))
        assert not message_contains("memory")(rec({}, "all fine"))

    def test_combinators(self):
        both = all_of(field_equals("s", 1), field_equals("t", 2))
        assert both(rec({"s": 1, "t": 2}))
        assert not both(rec({"s": 1, "t": 3}))
        either = any_of(field_equals("s", 1), field_equals("s", 2))
        assert either(rec({"s": 2}))

    def test_rulepack_evaluate(self):
        pack = RulePack("test")
        pack.add("big", "over 100", "warning", field_above("v", 100))
        hits = pack.evaluate([rec({"v": 150}), rec({"v": 50}), rec({"v": 200})])
        assert len(hits) == 1
        assert len(hits[0].hits) == 2

    def test_default_pack_finds_5xx(self):
        pack = default_pack()
        hits = pack.evaluate([rec({"status": 503}), rec({"status": 200})])
        names = {r.name for r in hits}
        assert "server-error" in names
        assert "client-error" not in names

    def test_default_pack_slow(self):
        pack = default_pack()
        hits = pack.evaluate([rec({"duration_ms": 2500})])
        assert any(r.name == "slow-request" for r in hits)
