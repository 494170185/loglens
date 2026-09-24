"""M13 — lexer for the filter expression language.

Grammar (M14 parses it):

    expr    := or
    or      := and (OR and)*
    and     := not (AND not)*
    not     := NOT not | primary
    primary := '(' expr ')' | comparison | word
    comparison := field op value
    op      := = != ~= < <= > >= IN CONTAINS
    value   := quoted string | bareword | number
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Token:
    kind: str  # LPAREN RPAREN AND OR NOT OP WORD STRING NUMBER EOF
    value: str
    pos: int

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Token({self.kind}, {self.value!r})"


class LexError(Exception):
    def __init__(self, message: str, pos: int):
        super().__init__(f"{message} (at position {pos})")
        self.pos = pos


_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<op>!=|~=|<=|>=|=|<|>)
  | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<word>[^\s()!=<>~]+)
    """,
    re.VERBOSE,
)

_KEYWORDS = {"and": "AND", "or": "OR", "not": "NOT", "in": "OP", "contains": "OP"}


def tokenize(text: str) -> list[Token]:
    """Split *text* into tokens; raises :class:`LexError` on bad input."""
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise LexError(f"unexpected character {text[pos]!r}", pos)
        if m.lastgroup == "op":
            # reject malformed glued operators like '===' or '=!'
            lookahead = m.end()
            if lookahead < len(text) and text[lookahead] in "!=<>~":
                raise LexError("malformed operator", pos)
        kind = m.lastgroup
        value = m.group()
        pos = m.end()
        if kind == "ws":
            continue
        elif kind == "string":
            tokens.append(Token("STRING", _unquote(value), m.start()))
        elif kind == "word":
            # A word that starts with a quote means the string never closed.
            if value[:1] in ('"', "'"):
                raise LexError(f"unterminated string starting {value[:1]!r}", m.start())
            lowered = value.lower()
            if lowered in _KEYWORDS:
                tokens.append(Token(_KEYWORDS[lowered], lowered, m.start()))
            else:
                tokens.append(Token("WORD", value, m.start()))
        elif kind == "number":
            tokens.append(Token("NUMBER", value, m.start()))
        elif kind == "op":
            tokens.append(Token("OP", value, m.start()))
        elif kind == "lparen":
            tokens.append(Token("LPAREN", value, m.start()))
        else:
            tokens.append(Token("RPAREN", value, m.start()))
    tokens.append(Token("EOF", "", pos))
    return tokens


def _unquote(quoted: str) -> str:
    quote = quoted[0]
    body = quoted[1:-1]
    escapes = {'\\"': '"', "\\'": "'", "\\\\": "\\", "\\n": "\n", "\\t": "\t"}
    for raw, cooked in escapes.items():
        body = body.replace(raw, cooked)
    if quote == '"':
        # no further processing for double quotes
        pass
    return body
