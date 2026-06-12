import pytest

from theseus_ship.grammar import detect_language, load_grammar


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


class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language("test.py") == "python"

    def test_python_stubs(self) -> None:
        assert detect_language("test.pyi") == "python"

    def test_unknown_extension(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect language"):
            detect_language("test.rs")

    def test_no_extension(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect language"):
            detect_language("Makefile")


class TestLoadGrammar:
    def test_unsupported_language(self) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            load_grammar("rust")
