import pytest

from nappe.grammar import detect_language, load_grammar


class TestGrammar:
    def test_load_python(self) -> None:
        grammar = load_grammar("python")
        assert grammar.language is not None
        assert grammar.name == "python"

    def test_is_error_node_error(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_error_node("ERROR") is True

    def test_is_error_node_missing(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_error_node("MISSING") is True

    def test_is_error_node_normal(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_error_node("if_statement") is False

    def test_unwrap_compatible_kinds(self) -> None:
        grammar = load_grammar("python")
        kinds = grammar.unwrap_compatible_kinds("block")
        assert "block" in kinds

    def test_is_protected_node_comment(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_protected_node("comment") is True

    def test_is_protected_node_normal(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_protected_node("assignment") is False


class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language("test.py") == "python"

    def test_python_stubs(self) -> None:
        assert detect_language("test.pyi") == "python"

    def test_unknown_extension(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect language"):
            detect_language("test.xyz")

    def test_no_extension(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect language"):
            detect_language("Makefile")


class TestLoadGrammar:
    def test_unsupported_language(self) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            load_grammar("ruby")


class TestSubtypes:
    def test_expression_subtypes(self) -> None:
        grammar = load_grammar("python")
        subtypes = grammar.subtypes("expression")
        assert "expression" in subtypes
        assert "primary_expression" in subtypes
        assert "boolean_operator" in subtypes
        assert "comparison_operator" in subtypes
        assert "conditional_expression" in subtypes

    def test_primary_expression_subtypes(self) -> None:
        grammar = load_grammar("python")
        subtypes = grammar.subtypes("primary_expression")
        assert "primary_expression" in subtypes
        assert "identifier" in subtypes
        assert "integer" in subtypes
        assert "call" in subtypes

    def test_unknown_kind_returns_self(self) -> None:
        grammar = load_grammar("python")
        subtypes = grammar.subtypes("nonexistent_kind")
        assert subtypes == frozenset({"nonexistent_kind"})


class TestIsSubtype:
    def test_identifier_is_subtype_of_expression(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_subtype("identifier", "expression") is True

    def test_integer_is_subtype_of_expression(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_subtype("integer", "expression") is True

    def test_if_statement_not_subtype_of_expression(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_subtype("if_statement", "expression") is False

    def test_primary_expression_is_subtype_of_expression(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_subtype("primary_expression", "expression") is True

    def test_kind_is_subtype_of_self(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_subtype("expression", "expression") is True


class TestFieldNameForChild:
    def test_function_definition_fields(self) -> None:
        grammar = load_grammar("python")
        assert grammar.field_name_for_child("function_definition", 1) == "name"
        assert grammar.field_name_for_child("function_definition", 2) == "parameters"
        assert grammar.field_name_for_child("function_definition", 4) == "body"

    def test_assignment_fields(self) -> None:
        grammar = load_grammar("python")
        assert grammar.field_name_for_child("assignment", 0) == "left"
        assert grammar.field_name_for_child("assignment", 2) == "right"

    def test_unknown_kind_returns_none(self) -> None:
        grammar = load_grammar("python")
        assert grammar.field_name_for_child("nonexistent_kind", 0) is None

    def test_non_field_position_returns_none(self) -> None:
        grammar = load_grammar("python")
        assert grammar.field_name_for_child("function_definition", 0) is None
