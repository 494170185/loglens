"""M14 — filter parser, AST and evaluation."""

from __future__ import annotations

import pytest

from loglens.filters.parser import (
    AndNode,
    CompareNode,
    NotNode,
    OrNode,
    ParseError,
    WordNode,
    compile_filter,
)


def ctx(**kw):
    base = {"message": "", "raw": ""}
    base.update(kw)
    return base


class TestParsing:
    def test_word_expression(self):
        f = compile_filter("error")
        assert isinstance(f.ast, WordNode)

    def test_comparison_ast(self):
        f = compile_filter("status = 404")
        assert isinstance(f.ast, CompareNode)
        assert f.ast.field == "status"
        assert f.ast.value == 404

    def test_and_or_precedence(self):
        f = compile_filter("a and b or c")
        # or is root: (a and b) or c
        assert isinstance(f.ast, OrNode)
        assert isinstance(f.ast.left, AndNode)

    def test_not_binds_tighter_than_and(self):
        f = compile_filter("not a and b")
        assert isinstance(f.ast, AndNode)
        assert isinstance(f.ast.left, NotNode)

    def test_parens_group(self):
        f = compile_filter("a or (b and c)")
        assert isinstance(f.ast, OrNode)
        assert isinstance(f.ast.right, AndNode)

    def test_double_not(self):
        f = compile_filter("not not a")
        assert isinstance(f.ast, NotNode)
        assert isinstance(f.ast.child, NotNode)


class TestEvaluationComparisons:
    def test_string_equality(self):
        assert compile_filter("level = error").matches(ctx(level="error"))

    def test_number_equality(self):
        assert compile_filter("status = 404").matches(ctx(status=404))
        assert compile_filter("status = 404").matches(ctx(status="404"))

    def test_inequality(self):
        assert compile_filter("level != error").matches(ctx(level="info"))
        assert not compile_filter("level != error").matches(ctx(level="error"))

    def test_missing_field_inequality_only(self):
        assert compile_filter("level != error").matches(ctx())
        assert not compile_filter("level = error").matches(ctx())
        assert not compile_filter("level > 5").matches(ctx())

    def test_numeric_ordering(self):
        assert compile_filter("status >= 500").matches(ctx(status=500))
        assert compile_filter("status >= 500").matches(ctx(status=502))
        assert not compile_filter("status >= 500").matches(ctx(status=404))
        assert compile_filter("latency < 0.5").matches(ctx(latency=0.25))
        assert compile_filter("latency > 100").matches(ctx(latency="120"))

    def test_non_numeric_ordering_is_false(self):
        assert not compile_filter("level > abc").matches(ctx(level="x"))

    def test_contains_substring(self):
        assert compile_filter("msg contains time").matches(ctx(msg="out of time"))
        assert not compile_filter("msg contains space").matches(ctx(msg="time"))

    def test_regex_match(self):
        assert compile_filter("path ~= ^/api/").matches(ctx(path="/api/v1"))
        assert not compile_filter("path ~= ^/api/$").matches(ctx(path="/api/v1"))

    def test_bad_regex_is_false_not_crash(self):
        # ( and ) are grammar characters, so use an unclosed-bracket pattern
        assert not compile_filter("path ~= [unclosed").matches(ctx(path="x"))

    def test_in_list(self):
        f = compile_filter("status in 500")
        assert f.matches(ctx(status=500))
        assert not f.matches(ctx(status=200))

    def test_in_list_literal(self):
        f = compile_filter("status in [500]")
        assert f.matches(ctx(status="[500]") )


class TestEvaluationLogic:
    def test_and(self):
        f = compile_filter("level = error and status = 500")
        assert f.matches(ctx(level="error", status=500))
        assert not f.matches(ctx(level="error", status=200))

    def test_or(self):
        f = compile_filter("level = error or level = warn")
        assert f.matches(ctx(level="error"))
        assert f.matches(ctx(level="warn"))
        assert not f.matches(ctx(level="info"))

    def test_not(self):
        f = compile_filter("not level = error")
        assert f.matches(ctx(level="info"))
        assert not f.matches(ctx(level="error"))

    def test_word_searches_message_and_raw(self):
        f = compile_filter("timeout")
        assert f.matches(ctx(message="connection timeout after 5s"))
        assert f.matches(ctx(raw="TIMEOUT occurred", message=""))

    def test_complex_expression(self):
        f = compile_filter(
            "level = error and (status >= 500 or msg contains fatal) and not host = canary"
        )
        assert f.matches(ctx(level="error", status=503, host="prod-1"))
        assert f.matches(ctx(level="error", msg="fatal error", host="prod-1"))
        assert not f.matches(ctx(level="error", status=200, msg="ok"))
        assert not f.matches(ctx(level="error", status=503, host="canary"))


class TestErrors:
    def test_empty_expression(self):
        with pytest.raises(ParseError):
            compile_filter("")

    def test_unbalanced_paren(self):
        with pytest.raises(ParseError):
            compile_filter("(a or b")

    def test_dangling_operator(self):
        with pytest.raises(ParseError):
            compile_filter("status =")

    def test_leading_operator(self):
        with pytest.raises(ParseError):
            compile_filter("= 5")

    def test_trailing_garbage(self):
        with pytest.raises(ParseError):
            compile_filter("a b c and")  # a b -> word word, then 'c and' -> err

    def test_bad_lex_becomes_parse_error(self):
        with pytest.raises(ParseError):
            compile_filter('msg = "unterminated')


class TestCallable:
    def test_filter_is_callable(self):
        f = compile_filter("a = 1")
        assert f(ctx(a=1)) is True
