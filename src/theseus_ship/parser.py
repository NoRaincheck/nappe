from __future__ import annotations

from tree_sitter import Parser, Node

from theseus_ship.grammar import Grammar
from theseus_ship.tree import NodeInfo, ParseResult


def _count_tokens(node: Node) -> int:
    if not node.children:
        return 1
    return sum(_count_tokens(child) for child in node.children)


def _has_errors(node: Node, grammar: Grammar) -> bool:
    if grammar.is_error_node(node.type):
        return True
    return any(_has_errors(child, grammar) for child in node.children)


def _child_kinds(node: Node) -> tuple[str, ...]:
    return tuple(child.type for child in node.children)


def _walk_tree(node: Node, grammar: Grammar) -> tuple[list[NodeInfo], int]:
    nodes: list[NodeInfo] = []
    error_count = 0

    info = NodeInfo(
        kind=node.type,
        byte_start=node.start_byte,
        byte_end=node.end_byte,
        token_count=_count_tokens(node),
        has_errors=_has_errors(node, grammar),
        child_kinds=_child_kinds(node),
    )
    nodes.append(info)
    if info.has_errors:
        error_count += 1

    for child in node.children:
        child_nodes, child_errors = _walk_tree(child, grammar)
        nodes.extend(child_nodes)
        error_count += child_errors

    return nodes, error_count


def parse_source(source: bytes, grammar: Grammar) -> ParseResult:
    parser = Parser()
    parser.language = grammar.language
    tree = parser.parse(source)

    all_nodes, error_count = _walk_tree(tree.root_node, grammar)
    root = (
        all_nodes[0]
        if all_nodes
        else NodeInfo(
            kind="ERROR",
            byte_start=0,
            byte_end=0,
            token_count=0,
            has_errors=True,
            child_kinds=(),
        )
    )

    all_nodes.sort(key=lambda n: n.token_count, reverse=True)

    return ParseResult(
        source_bytes=source,
        root_node=root,
        all_nodes=all_nodes,
        error_node_count=error_count,
    )


def has_syntax_errors(result: ParseResult) -> bool:
    return result.error_node_count > 0
