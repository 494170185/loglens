"""M16 — group-by aggregation."""

from __future__ import annotations

from loglens.aggregate import (
    Group,
    field_value,
    group_by,
    multi_group_by,
    render_key,
    sort_groups,
)
from loglens.model import Record


def rec(fields, **kw):
    return Record(raw="", message=kw.get("message", ""), fields=fields)


class TestFieldValue:
    def test_direct_field(self):
        assert field_value(rec({"status": 500}), "status") == 500

    def test_missing_is_none(self):
        assert field_value(rec({}), "status") is None

    def test_dotted_path(self):
        r = rec({"http": {"status": 404}})
        assert field_value(r, "http.status") == 404

    def test_builtin_level(self):
        assert field_value(Record(raw="", level="error"), "level") == "error"


class TestRenderKey:
    def test_none_renders_missing(self):
        assert render_key(None) == "(missing)"

    def test_empty_string(self):
        assert render_key("") == "(empty)"

    def test_bool(self):
        assert render_key(True) == "true"

    def test_number(self):
        assert render_key(500) == "500"


class TestGroupBy:
    def test_basic_grouping(self):
        records = [
            rec({"status": 500}),
            rec({"status": 500}),
            rec({"status": 200}),
        ]
        groups = group_by(records, "status")
        assert len(groups) == 2
        by_key = {g.key: g.count for g in groups}
        assert by_key == {"500": 2, "200": 1}

    def test_first_appearance_order(self):
        records = [rec({"host": "b"}), rec({"host": "a"}), rec({"host": "b"})]
        groups = group_by(records, "host")
        assert [g.key for g in groups] == ["b", "a"]

    def test_key_function(self):
        records = [rec({}), rec({}), rec({})]
        groups = group_by(records, lambda _r: "all")
        assert len(groups) == 1 and groups[0].count == 3

    def test_missing_groups_together(self):
        records = [rec({"host": "a"}), rec({}), rec({})]
        groups = group_by(records, "host")
        keys = [g.key for g in groups]
        assert "(missing)" in keys

    def test_group_numeric_values(self):
        records = [rec({"dur": 10}), rec({"dur": "20"}), rec({"dur": "x"})]
        groups = group_by(records, "host")
        g = groups[0]
        g.records = records
        assert sorted(g.numeric_values("dur")) == [10.0, 20.0]

    def test_group_first(self):
        g = Group(key="k", records=[rec({"a": 1}), rec({"a": 2})])
        assert g.first("a") == 1


class TestMultiGroup:
    def test_composite_key(self):
        records = [
            rec({"status": 500, "host": "a"}),
            rec({"status": 200, "host": "a"}),
            rec({"status": 500, "host": "b"}),
        ]
        groups = multi_group_by(records, ("host", "status"))
        keys = {g.key for g in groups}
        assert keys == {"a / 500", "a / 200", "b / 500"}


class TestSortGroups:
    def test_sort_by_count_desc(self):
        records = [rec({"k": "a"}), rec({"k": "b"}), rec({"k": "b"})]
        groups = sort_groups(group_by(records, "k"), by="count")
        assert groups[0].key == "b"

    def test_sort_by_count_asc(self):
        records = [rec({"k": "a"}), rec({"k": "b"}), rec({"k": "b"})]
        groups = sort_groups(group_by(records, "k"), by="count", reverse=False)
        assert groups[0].key == "a"

    def test_sort_by_avg(self):
        records = [
            rec({"k": "a", "dur": 10}),
            rec({"k": "a", "dur": 30}),
            rec({"k": "b", "dur": 100}),
        ]
        groups = sort_groups(group_by(records, "k"), by="avg:dur")
        assert groups[0].key == "b"
