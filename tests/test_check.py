from pathlib import Path

import pytest

from nappe.grammar import load_grammar
from nappe.checker import (
    check_constant_expressions,
    check_dead_classes,
    check_dead_functions,
    check_redundant_newlines,
    check_redundant_parens,
    check_trailing_whitespace,
    check_unnecessary_semicolons,
    check_unused_assignments,
)
from nappe.diff import apply_fixes, format_text
from nappe.rules import FixSafety


class TestCheckTrailingWhitespace:
    def test_finds_trailing_spaces(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1   \ny = 2\n"
        suggestions = check_trailing_whitespace(source, grammar, "test.py")
        assert len(suggestions) == 1
        assert suggestions[0].rule.code == "RED203"

    def test_no_trailing_spaces(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\ny = 2\n"
        suggestions = check_trailing_whitespace(source, grammar, "test.py")
        assert len(suggestions) == 0


class TestCheckRedundantNewlines:
    def test_finds_redundant_newlines(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\n\n"
        suggestions = check_redundant_newlines(source, grammar, "test.py")
        assert len(suggestions) == 1
        assert suggestions[0].rule.code == "RED204"

    def test_single_newline_ok(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\n"
        suggestions = check_redundant_newlines(source, grammar, "test.py")
        assert len(suggestions) == 0


class TestCheckUnnecessarySemicolons:
    def test_finds_semicolons(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1;\ny = 2\n"
        suggestions = check_unnecessary_semicolons(source, grammar, "test.py")
        assert len(suggestions) == 1
        assert suggestions[0].rule.code == "RED202"

    def test_no_semicolons(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\ny = 2\n"
        suggestions = check_unnecessary_semicolons(source, grammar, "test.py")
        assert len(suggestions) == 0


class TestCheckRedundantParens:
    def test_finds_redundant_parens(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2)\n"
        suggestions = check_redundant_parens(source, grammar, "test.py")
        assert len(suggestions) >= 1
        assert any(s.rule.code == "RED201" for s in suggestions)


class TestCheckConstantExpressions:
    def test_finds_constant_addition(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 + 2\n"
        suggestions = check_constant_expressions(source, grammar, "test.py")
        assert len(suggestions) >= 1
        assert any(s.rule.code == "RED200" for s in suggestions)

    def test_no_constant_expressions(self) -> None:
        grammar = load_grammar("python")
        source = b"x = y + z\n"
        suggestions = check_constant_expressions(source, grammar, "test.py")
        assert len(suggestions) == 0


class TestCheckDeadFunctions:
    def test_finds_dead_function(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo():\n    return 1\n\ndef bar():\n    return foo()\n\nbar()\n"
        suggestions = check_dead_functions(source, grammar, "test.py")
        assert len(suggestions) == 0

    def test_finds_uncalled_function(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo():\n    return 1\n\nx = 1\n"
        suggestions = check_dead_functions(source, grammar, "test.py")
        assert len(suggestions) == 1
        assert suggestions[0].rule.code == "RED100"


class TestCheckDeadClasses:
    def test_finds_dead_class(self) -> None:
        grammar = load_grammar("python")
        source = b"class MyClass:\n    pass\n\nx = 1\n"
        suggestions = check_dead_classes(source, grammar, "test.py")
        assert len(suggestions) == 1
        assert suggestions[0].rule.code == "RED101"


class TestCheckUnusedAssignments:
    def test_finds_unused_assignment(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\ny = 2\n"
        suggestions = check_unused_assignments(source, grammar, "test.py")
        assert len(suggestions) >= 1
        assert any(s.rule.code == "RED102" for s in suggestions)


class TestFormatText:
    def test_empty_suggestions(self) -> None:
        assert format_text([]) == ""

    def test_with_suggestions(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 + 2\n"
        suggestions = check_constant_expressions(source, grammar, "test.py")
        output = format_text(suggestions)
        assert "RED200" in output
        assert "Found" in output


class TestApplyFixes:
    def test_apply_safe_fixes(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1   \n"
        suggestions = check_trailing_whitespace(source, grammar, "test.py")
        fixes = apply_fixes(suggestions, FixSafety.SAFE)
        assert "test.py" in fixes
        assert fixes["test.py"] == b"x = 1\n"
