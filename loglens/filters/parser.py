"""M14 — recursive descent parser and AST for filter expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loglens.filters.lexer import LexError, Token, tokenize


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"{message} (near {token.value!r} at position {token.pos})")
        self.token = token


@dataclass
class Node:
    """Base class for expression AST nodes."""

    def evaluate(self, context: dict[str, Any]) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass
class OrNode(Node):
    left: Node
    right: Node

    def evaluate(self, context: dict[str, Any]) -> bool:
        return self.left.evaluate(context) or self.right.evaluate(context)


@dataclass
class AndNode(Node):
    left: Node
    right: Node

    def evaluate(self, context: dict[str, Any]) -> bool:
        return self.left.evaluate(context) and self.right.evaluate(context)


@dataclass
class NotNode(Node):
    child: Node

    def evaluate(self, context: dict[str, Any]) -> bool:
        return not self.child.evaluate(context)


@dataclass
class WordNode(Node):
    """A bare word matches anywhere in the message/raw text."""

    word: str

    def evaluate(self, context: dict[str, Any]) -> bool:
        haystack = f"{context.get('message', '')} {context.get('raw', '')}"
        return self.word.lower() in haystack.lower()


@dataclass
class CompareNode(Node):
    field: str
    op: str
    value: Any

    def evaluate(self, context: dict[str, Any]) -> bool:
        actual = context.get(self.field, _MISSING)
        return compare_values(actual, self.op, self.value)


_MISSING = object()


def compare_values(actual: Any, op: str, expected: Any) -> bool:
    """Apply a comparison operator; missing fields only satisfy ``!=``."""
    if actual is _MISSING:
        return op == "!="
    # numeric comparisons when both sides can be numbers
    if op in ("<", "<=", ">", ">="):
        a_num, b_num = _as_number(actual), _as_number(expected)
        if a_num is not None and b_num is not None:
            return _ORDER_OPS[op](a_num, b_num)
        return False
    if op == "in":
        candidates = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return _render(actual) in [_render(c) for c in candidates]
    if op == "contains":
        return str(expected).lower() in _render(actual).lower()
    if op == "~=":
        import re

        try:
            return re.search(str(expected), _render(actual)) is not None
        except re.error:
            return False
    a_text, b_text = _render(actual), _render(expected)
    if op == "=":
        return a_text == b_text
    if op == "!=":
        return a_text != b_text
    raise ValueError(f"unknown operator {op!r}")  # pragma: no cover - parser guards


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _render(value: Any) -> str:
    from loglens.parsers.jsonl import render_value

    if value is _MISSING:
        return ""
    if isinstance(value, str):
        return value
    return render_value(value)


import operator  # noqa: E402

_ORDER_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


class Parser:
    """Recursive descent parser over the token stream.

    expr := or ; or := and (OR and)* ; and := not (AND not)*
    not := NOT not | primary ; primary := '(' expr ')' | comparison | word
    comparison := WORD OP value
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def parse(self) -> Node:
        if self.current.kind == "EOF":
            raise ParseError("empty expression", self.current)
        node = self.parse_or()
        if self.current.kind != "EOF":
            raise ParseError("unexpected trailing tokens", self.current)
        return node

    def parse_or(self) -> Node:
        node = self.parse_and()
        while self.current.kind == "OR":
            self.advance()
            node = OrNode(node, self.parse_and())
        return node

    def parse_and(self) -> Node:
        node = self.parse_not()
        while self.current.kind == "AND":
            self.advance()
            node = AndNode(node, self.parse_not())
        return node

    def parse_not(self) -> Node:
        if self.current.kind == "NOT":
            self.advance()
            return NotNode(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        if self.current.kind == "LPAREN":
            self.advance()
            node = self.parse_or()
            if self.current.kind != "RPAREN":
                raise ParseError("expected closing parenthesis", self.current)
            self.advance()
            return node
        if self.current.kind == "WORD":
            word = self.advance()
            if self.current.kind == "OP":
                op = self.advance()
                if self.current.kind in ("WORD", "STRING", "NUMBER"):
                    value_token = self.advance()
                    return CompareNode(word.value, op.value, _literal(value_token))
                raise ParseError("expected value after operator", self.current)
            return WordNode(word.value)
        raise ParseError("expected a field, word or parenthesis", self.current)


def _literal(token: Token) -> Any:
    if token.kind == "NUMBER":
        return float(token.value) if "." in token.value else int(token.value)
    return token.value


@dataclass
class Filter:
    """A compiled filter expression; call :meth:`matches` per record."""

    source: str
    ast: Node = field(repr=False, default=None)  # type: ignore[assignment]

    def matches(self, context: dict[str, Any]) -> bool:
        return self.ast.evaluate(context)

    def __call__(self, context: dict[str, Any]) -> bool:
        return self.matches(context)


def compile_filter(text: str) -> Filter:
    """Parse *text* into an executable :class:`Filter`."""
    try:
        tokens = tokenize(text)
    except LexError as exc:
        raise ParseError(str(exc), Token("EOF", "", exc.pos)) from exc
    ast = Parser(tokens).parse()
    return Filter(source=text, ast=ast)
