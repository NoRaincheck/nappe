from pathlib import Path

from theseus_ship.grammar import load_grammar
from theseus_ship.parser import parse_source, has_syntax_errors


FIXTURES = Path(__file__).parent / "fixtures"


class TestParseSource:
    def test_simple_python(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\n"
        result = parse_source(source, grammar)

        assert result.root_node.kind == "module"
        assert result.source_bytes == source
        assert result.error_node_count == 0
        assert not has_syntax_errors(result)

    def test_node_metadata(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\n"
        result = parse_source(source, grammar)

        func_node = next(n for n in result.all_nodes if n.kind == "function_definition")
        assert func_node.byte_start >= 0
        assert func_node.byte_end > func_node.byte_start
        assert func_node.token_count > 0
        assert func_node.has_errors is False
        assert "block" in func_node.child_kinds

    def test_largest_first_ordering(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        result = parse_source(source, grammar)

        token_counts = [n.token_count for n in result.all_nodes]
        assert token_counts == sorted(token_counts, reverse=True)

    def test_with_parse_errors(self) -> None:
        grammar = load_grammar("python")
        source = (FIXTURES / "parse_error.py").read_bytes()
        result = parse_source(source, grammar)

        assert result.error_node_count > 0
        assert has_syntax_errors(result)

    def test_valid_file_no_errors(self) -> None:
        grammar = load_grammar("python")
        source = (FIXTURES / "simple.py").read_bytes()
        result = parse_source(source, grammar)

        assert not has_syntax_errors(result)

    def test_complex_file(self) -> None:
        grammar = load_grammar("python")
        source = (FIXTURES / "complex.py").read_bytes()
        result = parse_source(source, grammar)

        assert not has_syntax_errors(result)
        func_kinds = [n.kind for n in result.all_nodes if n.kind == "function_definition"]
        assert len(func_kinds) >= 3

    def test_empty_source(self) -> None:
        grammar = load_grammar("python")
        result = parse_source(b"", grammar)
        assert result.root_node.kind == "module"
        assert result.root_node.token_count == 1
        assert result.root_node.child_kinds == ()
