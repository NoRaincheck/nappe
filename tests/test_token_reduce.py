from __future__ import annotations

import pytest

from nappe.grammar import load_grammar
from nappe.parser import parse_source
from nappe.token_reduce import (
    _remove_redundant_parens,
    _strip_trailing_newlines,
    _strip_trailing_whitespace,
    token_reduce,
)


@pytest.fixture
def grammar():
    return load_grammar("python")


class TestStripTrailingWhitespace:
    def test_removes_trailing_spaces(self, grammar):
        source = b"x = 1   \ny = 2\n"
        result = _strip_trailing_whitespace(source)
        assert result == b"x = 1\ny = 2\n"

    def test_removes_trailing_tabs(self, grammar):
        source = b"x = 1\t\ny = 2\n"
        result = _strip_trailing_whitespace(source)
        assert result == b"x = 1\ny = 2\n"

    def test_no_change(self, grammar):
        source = b"x = 1\ny = 2\n"
        result = _strip_trailing_whitespace(source)
        assert result is None

    def test_preserves_leading_whitespace(self, grammar):
        source = b"    x = 1\n"
        result = _strip_trailing_whitespace(source)
        assert result is None


class TestStripTrailingNewlines:
    def test_removes_extra_newlines(self, grammar):
        source = b"x = 1\n\n\n"
        result = _strip_trailing_newlines(source)
        assert result == b"x = 1\n"

    def test_no_change(self, grammar):
        source = b"x = 1\n"
        result = _strip_trailing_newlines(source)
        assert result is None

    def test_no_trailing_newline(self, grammar):
        source = b"x = 1"
        result = _strip_trailing_newlines(source)
        assert result is None


class TestRemoveRedundantParens:
    def test_removes_redundant_parens(self, grammar):
        source = b"x = (1 + 2)\n"
        result = _remove_redundant_parens(source, grammar)
        assert result == b"x = 1 + 2\n"

    def test_keeps_necessary_parens_via_interestingness(self, grammar):
        source = b"x = (1 + 2) * 3\n"
        original = source
        def is_interesting(s):
            return b"(1 + 2)" in s
        result = token_reduce(source, grammar, is_interesting)
        assert result == original

    def test_keeps_tuple_parens(self, grammar):
        source = b"x = (1,)\n"
        result = _remove_redundant_parens(source, grammar)
        assert result == source


class TestTokenReduce:
    def test_reduces_whitespace(self, grammar):
        source = b"x = 1   \ny = 2   \n"
        result = token_reduce(source, grammar, lambda s: True)
        assert result == b"x = 1\ny = 2\n"

    def test_removes_trailing_newlines(self, grammar):
        source = b"x = 1\n\n\n"
        result = token_reduce(source, grammar, lambda s: True)
        assert result == b"x = 1\n"

    def test_respects_interesting(self, grammar):
        source = b"x = 1   \ny = 2\n"
        result = token_reduce(source, grammar, lambda s: False)
        assert result == source

    def test_preserves_valid_syntax(self, grammar):
        source = b"def foo():\n    pass\n\n"
        result = token_reduce(source, grammar, lambda s: True)
        parsed = parse_source(result, grammar)
        assert parsed.error_node_count == 0

    def test_auto_reduce_pipeline(self, grammar):
        source = b"def foo(): pass\ndef bar(): pass\n\n"
        from nappe.reducer import Reducer

        reducer = Reducer(grammar, auto=True, quiet=True)
        result = reducer.reduce(source)
        final = parse_source(result.source, grammar)
        assert final.error_node_count == 0

    def test_noop_on_minimal_source(self, grammar):
        source = b"pass\n"
        result = token_reduce(source, grammar, lambda s: True)
        assert result == source

    def test_reduces_multiple_whitespace_types(self, grammar):
        source = b"x = 1  \ny = 2\t\nz = 3   \n"
        result = token_reduce(source, grammar, lambda s: True)
        assert b"  " not in result
        assert b"\t\n" not in result

    def test_removes_redundant_parens(self, grammar):
        source = b"x = (1 + 2)\ny = (3)\n"
        result = token_reduce(source, grammar, lambda s: True)
        assert b"x = 1 + 2\n" in result
