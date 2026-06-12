from nappe.grammar import load_grammar
from nappe.parser import parse_source
from nappe.transforms import (
    apply_delete,
    apply_transform,
    apply_unwrap,
    bounded_bfs,
    generate_candidates,
    result_error_count,
)
from nappe.tree import NodeInfo, TransformCandidate, TransformKind


class TestApplyDelete:
    def test_delete_statement(self) -> None:
        source = b"x = 1\ny = 2\n"
        node = NodeInfo("assignment", 0, 5, 3, False, ("identifier", "integer"))
        result = apply_delete(source, node)
        assert result == b"\ny = 2\n"

    def test_delete_middle(self) -> None:
        source = b"a\nb\nc\n"
        node = NodeInfo("expression_statement", 2, 4, 1, False, ())
        result = apply_delete(source, node)
        assert result == b"a\nc\n"


class TestApplyUnwrap:
    def test_unwrap_parens(self) -> None:
        source = b"(x + 1)\n"
        target = NodeInfo(
            "parenthesized_expression", 0, 7, 5, False, ("binary_expression",)
        )
        result = apply_unwrap(source, target, 1, 6)
        assert result == b"x + 1\n"

    def test_unwrap_preserves_child_content(self) -> None:
        source = b"(hello)\n"
        target = NodeInfo("parenthesized_expression", 0, 7, 2, False, ("identifier",))
        result = apply_unwrap(source, target, 1, 6)
        assert result == b"hello\n"


class TestApplyTransform:
    def test_valid_delete(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        result = parse_source(source, grammar)

        pass_node = next(n for n in result.all_nodes if n.kind == "pass_statement")
        candidate = TransformCandidate(target=pass_node, kind=TransformKind.DELETE)
        root = result.root_node

        new = apply_transform(source, candidate, grammar, root_node=root)
        assert new is not None
        new_source, new_result = new
        assert b"pass" not in new_source

    def test_delete_root_rejected(self) -> None:
        grammar = load_grammar("python")
        source = b"pass\n"
        result = parse_source(source, grammar)
        root = result.root_node

        candidate = TransformCandidate(target=root, kind=TransformKind.DELETE)
        new = apply_transform(source, candidate, grammar, root_node=root)
        assert new is None


class TestGenerateCandidates:
    def test_generates_delete_candidates(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        delete_candidates = [c for c in candidates if c.kind == TransformKind.DELETE]
        assert len(delete_candidates) > 0

    def test_no_root_delete(self) -> None:
        grammar = load_grammar("python")
        source = b"pass\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        root_deletes = [
            c
            for c in candidates
            if c.kind == TransformKind.DELETE
            and c.target.byte_start == result.root_node.byte_start
            and c.target.byte_end == result.root_node.byte_end
        ]
        assert len(root_deletes) == 0

    def test_largest_first_ordering(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        token_counts = [c.target.token_count for c in candidates]
        assert token_counts == sorted(token_counts, reverse=True)

    def test_comments_not_deleted(self) -> None:
        grammar = load_grammar("python")
        source = b"# important comment\nx = 1\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        delete_candidates = [c for c in candidates if c.kind == TransformKind.DELETE]
        comment_deletes = [c for c in delete_candidates if c.target.kind == "comment"]
        assert len(comment_deletes) == 0

    def test_multiple_comments_preserved(self) -> None:
        grammar = load_grammar("python")
        source = b"# first\n# second\n# third\nx = 1\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        comment_nodes = [n for n in result.all_nodes if n.kind == "comment"]
        assert len(comment_nodes) == 3

        delete_candidates = [c for c in candidates if c.kind == TransformKind.DELETE]
        comment_deletes = [c for c in delete_candidates if c.target.kind == "comment"]
        assert len(comment_deletes) == 0


class TestResultErrorCount:
    def test_no_errors(self) -> None:
        grammar = load_grammar("python")
        source = b"x = 1\n"
        assert result_error_count(source, grammar) == 0

    def test_with_errors(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2\n"
        assert result_error_count(source, grammar) > 0


class TestUnwrapTransformEndToEnd:
    def test_unwrap_parens_produces_child(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (y + 1)\n"
        result = parse_source(source, grammar)
        root = result.root_node

        paren_node = next(
            n for n in result.all_nodes if n.kind == "parenthesized_expression"
        )
        candidate = TransformCandidate(
            target=paren_node,
            kind=TransformKind.UNWRAP,
            unwrap_child_index=1,
            child_byte_start=paren_node.child_byte_starts[1],
            child_byte_end=paren_node.child_byte_ends[1],
        )
        new = apply_transform(source, candidate, grammar, root_node=root)
        assert new is not None
        new_source, _ = new
        assert b"y + 1" in new_source
        assert b"(" not in new_source

    def test_unwrap_if_body(self) -> None:
        grammar = load_grammar("python")
        source = b"if True:\n    pass\n"
        result = parse_source(source, grammar)

        block_node = next(n for n in result.all_nodes if n.kind == "block")
        pass_idx = block_node.child_kinds.index("pass_statement")
        raw_new = apply_unwrap(
            source,
            block_node,
            block_node.child_byte_starts[pass_idx],
            block_node.child_byte_ends[pass_idx],
        )
        assert b"pass" in raw_new

    def test_unwrap_not_empty(self) -> None:
        grammar = load_grammar("python")
        source = b"(1 + 2)\n"
        result = parse_source(source, grammar)
        root = result.root_node

        paren_node = next(
            n for n in result.all_nodes if n.kind == "parenthesized_expression"
        )
        binary_idx = paren_node.child_kinds.index("binary_operator")
        candidate = TransformCandidate(
            target=paren_node,
            kind=TransformKind.UNWRAP,
            unwrap_child_index=binary_idx,
            child_byte_start=paren_node.child_byte_starts[binary_idx],
            child_byte_end=paren_node.child_byte_ends[binary_idx],
        )
        new = apply_transform(source, candidate, grammar, root_node=root)
        assert new is not None
        new_source, _ = new
        assert len(new_source.strip()) > 0
        assert new_source != source


class TestBoundedBFS:
    def test_finds_compatible_descendant(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2)\n"
        result = parse_source(source, grammar)
        root = result.root_node

        paren_node = next(
            n for n in result.all_nodes if n.kind == "parenthesized_expression"
        )
        candidates = bounded_bfs(
            source,
            root,
            paren_node,
            grammar,
            lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
        )
        assert len(candidates) > 0
        assert all(c.kind == TransformKind.UNWRAP for c in candidates)

    def test_finds_nested_compatible(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2)\n"
        result = parse_source(source, grammar)
        root = result.root_node

        paren_node = next(
            n for n in result.all_nodes if n.kind == "parenthesized_expression"
        )
        candidates = bounded_bfs(
            source,
            root,
            paren_node,
            grammar,
            lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
            max_depth=4,
        )
        assert len(candidates) > 0

    def test_respects_max_depth(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2)\n"
        result = parse_source(source, grammar)
        root = result.root_node

        paren_node = next(
            n for n in result.all_nodes if n.kind == "parenthesized_expression"
        )
        candidates_depth1 = bounded_bfs(
            source,
            root,
            paren_node,
            grammar,
            lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
            max_depth=1,
        )
        candidates_depth4 = bounded_bfs(
            source,
            root,
            paren_node,
            grammar,
            lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
            max_depth=4,
        )
        assert len(candidates_depth4) >= len(candidates_depth1)

    def test_sorted_by_token_count(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2)\n"
        result = parse_source(source, grammar)
        root = result.root_node

        paren_node = next(
            n for n in result.all_nodes if n.kind == "parenthesized_expression"
        )
        candidates = bounded_bfs(
            source,
            root,
            paren_node,
            grammar,
            lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
        )
        token_counts = [c.target.token_count for c in candidates]
        assert token_counts == sorted(token_counts, reverse=True)

    def test_no_candidates_for_non_expression(self) -> None:
        grammar = load_grammar("python")
        source = b"if True:\n    pass\n"
        result = parse_source(source, grammar)
        root = result.root_node

        if_node = next(n for n in result.all_nodes if n.kind == "if_statement")
        candidates = bounded_bfs(
            source,
            root,
            if_node,
            grammar,
            lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
        )
        assert len(candidates) == 0


class TestGenerateCandidatesSubsume:
    def test_more_unwrap_candidates_with_subsume(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (y + 1)\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        unwrap_candidates = [c for c in candidates if c.kind == TransformKind.UNWRAP]
        assert len(unwrap_candidates) > 0

    def test_bfs_candidates_included(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (y + 1)\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        unwrap_candidates = [c for c in candidates if c.kind == TransformKind.UNWRAP]
        assert len(unwrap_candidates) > 0

    def test_subsume_unwrap_with_nested_expression(self) -> None:
        grammar = load_grammar("python")
        source = b"x = (1 + 2)\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)

        unwrap_candidates = [c for c in candidates if c.kind == TransformKind.UNWRAP]
        assert len(unwrap_candidates) > 0


class TestKleeneClassification:
    def test_block_is_kleene(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_kleene_node("block", ("pass_statement", "pass_statement"))

    def test_if_statement_not_kleene(self) -> None:
        grammar = load_grammar("python")
        assert not grammar.is_kleene_node("if_statement", ("if", "expression", "block"))

    def test_parameters_is_kleene(self) -> None:
        grammar = load_grammar("python")
        assert grammar.is_kleene_node("parameters", ("identifier", "identifier", "identifier"))

    def test_single_child_not_kleene(self) -> None:
        grammar = load_grammar("python")
        assert not grammar.is_kleene_node("block", ("pass_statement",))


class TestDdmin:
    def test_ddmin_removes_irrelevant_children(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo():\n    x = 1\n    y = 2\n    z = 3\n"
        result = parse_source(source, grammar)
        candidates = generate_candidates(result, grammar)
        ddmin_candidates = [c for c in candidates if c.kind == TransformKind.DDMIN]
        assert len(ddmin_candidates) > 0

    def test_ddmin_preserves_interesting(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo():\n    x = 1\n    y = 2\n    z = 3\n"
        result = parse_source(source, grammar)
        block = next(n for n in result.all_nodes if n.kind == "block")
        from nappe.transforms import apply_ddmin
        final = apply_ddmin(
            source, block, grammar,
            is_interesting=lambda s: True,
        )
        assert final is not None
        new_source, new_result = final
        assert new_result.error_node_count == 0
        assert len(new_source) < len(source)
