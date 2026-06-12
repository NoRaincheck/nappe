from nappe.escapes import (
    IdentifierOccurrence,
    remove_dead_assignment,
    shorten_identifier,
    simplify_expression,
    try_escape_transforms,
)
from nappe.grammar import load_grammar
from tree_sitter import Parser


def _get_first_node(source: bytes, grammar: load_grammar, node_type: str):
    parser = Parser()
    parser.language = grammar.language
    tree = parser.parse(source)

    def walk(node):
        if node.type == node_type:
            return node
        for child in node.children:
            result = walk(child)
            if result is not None:
                return result
        return None

    return walk(tree.root_node)


class TestSimplifyExpression:
    def test_simplify_addition(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 + 2\n"
        node = _get_first_node(source, grammar, "binary_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = 3\n"

    def test_simplify_multiplication(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 3 * 4\n"
        node = _get_first_node(source, grammar, "binary_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = 12\n"

    def test_simplify_subtraction(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 10 - 3\n"
        node = _get_first_node(source, grammar, "binary_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = 7\n"

    def test_simplify_division(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 10 / 2\n"
        node = _get_first_node(source, grammar, "binary_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = 5.0\n"

    def test_simplify_boolean_and_true(self) -> None:
        grammar = load_grammar("python")
        source = b"x = True and False\n"
        node = _get_first_node(source, grammar, "boolean_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = False\n"

    def test_simplify_boolean_or_true(self) -> None:
        grammar = load_grammar("python")
        source = b"x = True or False\n"
        node = _get_first_node(source, grammar, "boolean_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = True\n"

    def test_simplify_comparison(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 < 2\n"
        node = _get_first_node(source, grammar, "comparison_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = True\n"

    def test_simplify_comparison_equal(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 == 1\n"
        node = _get_first_node(source, grammar, "comparison_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result == b"x = True\n"

    def test_no_simplify_variable_expression(self) -> None:
        grammar = load_grammar("python")
        source = b"x = y + z\n"
        node = _get_first_node(source, grammar, "binary_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result is None

    def test_no_simplify_string_concat(self) -> None:
        grammar = load_grammar("python")
        source = b'x = "hello" + "world"\n'
        node = _get_first_node(source, grammar, "binary_operator")
        assert node is not None
        result = simplify_expression(source, node, grammar)
        assert result is None


class TestShortenIdentifier:
    def test_shorten_single_occurrence(self) -> None:
        source = b"my_variable = 1\n"
        occ = [IdentifierOccurrence("my_variable", 0, 11)]
        result = shorten_identifier(source, "my_variable", "a", occ)
        assert result == b"a = 1\n"

    def test_shorten_multiple_occurrences(self) -> None:
        source = b"my_variable = 1\nprint(my_variable)\n"
        occ = [
            IdentifierOccurrence("my_variable", 0, 11),
            IdentifierOccurrence("my_variable", 22, 33),
        ]
        result = shorten_identifier(source, "my_variable", "a", occ)
        assert result == b"a = 1\nprint(a)\n"

    def test_shorten_no_occurrences(self) -> None:
        source = b"x = 1\n"
        result = shorten_identifier(source, "x", "a", [])
        assert result == source

    def test_shorten_preserves_other_code(self) -> None:
        source = b"x = 1\ny = 2\n"
        occ = [IdentifierOccurrence("x", 0, 1)]
        result = shorten_identifier(source, "x", "z", occ)
        assert result == b"z = 1\ny = 2\n"


class TestRemoveDeadAssignment:
    def test_remove_dead_simple(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\n"
        node = _get_first_node(source, grammar, "assignment")
        assert node is not None
        result = remove_dead_assignment(source, node, grammar)
        assert result == b"\n"

    def test_remove_dead_used_after(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\ny = x\n"
        node = _get_first_node(source, grammar, "assignment")
        assert node is not None
        result = remove_dead_assignment(source, node, grammar)
        assert result is None

    def test_remove_dead_not_underscore(self) -> None:
        grammar = load_grammar("python")
        source = b"_ = 1\n"
        node = _get_first_node(source, grammar, "assignment")
        assert node is not None
        result = remove_dead_assignment(source, node, grammar)
        assert result is None

    def test_remove_dead_reassigned(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\ny = 2\n"
        node = _get_first_node(source, grammar, "assignment")
        assert node is not None
        result = remove_dead_assignment(source, node, grammar)
        assert result == b"\ny = 2\n"

    def test_remove_dead_augmented(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\nx += 1\n"
        node = _get_first_node(source, grammar, "augmented_assignment")
        assert node is not None
        result = remove_dead_assignment(source, node, grammar)
        assert result == b"x = 1\n\n"


class TestTryEscapeTransforms:
    def test_simplify_expression_escape(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 + 2\nprint(x)\n"
        result = try_escape_transforms(source, grammar, lambda s: True, max_attempts=10)
        assert b"3" in result

    def test_no_escape_on_uninteresting(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 + 2\n"
        result = try_escape_transforms(
            source, grammar, lambda s: False, max_attempts=10
        )
        assert result == source

    def test_dead_assignment_escape(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\ny = 2\n"
        result = try_escape_transforms(source, grammar, lambda s: True, max_attempts=10)
        assert b"x = 1" not in result or b"y = 2" not in result

    def test_max_attempts_limit(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1 + 2\nprint(x)\n"
        result = try_escape_transforms(source, grammar, lambda s: True, max_attempts=1)
        assert result != source
        assert len(result) < len(source)

    def test_multiple_transformations(self) -> None:
        grammar = load_grammar("python")
        source = b"a = 1 + 2\nb = 3 * 4\nprint(a, b)\n"
        result = try_escape_transforms(source, grammar, lambda s: True, max_attempts=10)
        assert b"3" in result
        assert b"12" in result
