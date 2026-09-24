"""M13 — filter expression lexer."""

from __future__ import annotations

import pytest

from loglens.filters.lexer import LexError, tokenize


class TestBasicTokens:
    def test_word(self):
        toks = tokenize("error")
        assert toks[0].kind == "WORD"
        assert toks[0].value == "error"
        assert toks[-1].kind == "EOF"

    def test_keywords_uppercase_kinds(self):
        toks = tokenize("a and b or not c")
        kinds = [t.kind for t in toks[:-1]]
        assert kinds == ["WORD", "AND", "WORD", "OR", "NOT", "WORD"]

    def test_operators(self):
        for op in ["=", "!=", "~=", "<", "<=", ">", ">="]:
            toks = tokenize(f"a {op} b")
            assert toks[1].kind == "OP"
            assert toks[1].value == op

    def test_in_and_contains_are_ops(self):
        toks = tokenize("status in 500")
        assert toks[1].kind == "OP"
        assert toks[1].value == "in"
        toks = tokenize("msg contains error")
        assert toks[1].value == "contains"

    def test_parens(self):
        toks = tokenize("(a or b)")
        kinds = [t.kind for t in toks[:-1]]
        assert kinds == ["LPAREN", "WORD", "OR", "WORD", "RPAREN"]


class TestLiterals:
    def test_double_quoted_string(self):
        toks = tokenize('msg = "hello world"')
        assert toks[2].kind == "STRING"
        assert toks[2].value == "hello world"

    def test_single_quoted_string(self):
        toks = tokenize("msg = 'single'")
        assert toks[2].value == "single"

    def test_escaped_quote_inside_string(self):
        toks = tokenize(r'msg = "say \"hi\""')
        assert toks[2].value == 'say "hi"'

    def test_numbers(self):
        toks = tokenize("status = 404")
        assert toks[2].kind == "NUMBER"
        assert toks[2].value == "404"

    def test_float_number(self):
        toks = tokenize("latency > 0.5")
        assert toks[2].kind == "NUMBER"
        assert toks[2].value == "0.5"

    def test_negative_number(self):
        toks = tokenize("delta < -3")
        assert toks[2].value == "-3"


class TestErrors:
    def test_unterminated_string(self):
        with pytest.raises(LexError):
            tokenize('msg = "oops')

    def test_bad_character(self):
        with pytest.raises(LexError):
            tokenize("a === b")

    def test_error_carries_position(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("a !# b")
        assert exc_info.value.pos >= 2


class TestWhitespace:
    def test_multiple_spaces_skipped(self):
        toks = tokenize("a   =    b")
        assert [t.kind for t in toks[:-1]] == ["WORD", "OP", "WORD"]

    def test_empty_input_only_eof(self):
        toks = tokenize("")
        assert len(toks) == 1
        assert toks[0].kind == "EOF"

    def test_leading_trailing_space(self):
        toks = tokenize("  word  ")
        assert toks[0].kind == "WORD"
