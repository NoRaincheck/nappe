from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Parser

from nappe.grammar import Grammar


@dataclass
class IdentifierOccurrence:
    name: str
    byte_start: int
    byte_end: int


def simplify_expression(source: bytes, node: Any, grammar: Grammar) -> bytes | None:
    node_text = source[node.start_byte : node.end_byte]
    result = _eval_constant(node_text)
    if result is None:
        return None
    replacement = result.encode("utf-8")
    if replacement == node_text:
        return None
    return source[: node.start_byte] + replacement + source[node.end_byte :]


def _eval_constant(text: bytes) -> str | None:
    s = text.decode("utf-8", errors="replace").strip()
    result = _safe_eval(s)
    if result is None:
        return None
    return str(result)


def _safe_eval(s: str) -> Any:
    allowed = set("0123456789+-*/%(). TrueFalsoandornotiIn<>=!")
    if not all(c in allowed or c.isspace() for c in s):
        return None
    try:
        result = eval(s)  # noqa: S307
        if isinstance(result, bool):
            return result
        if isinstance(result, int):
            return result
        if isinstance(result, float):
            return result
        return None
    except Exception:
        return None


def shorten_identifier(
    source: bytes,
    target_name: str,
    replacement: str,
    occurrences: list[IdentifierOccurrence],
) -> bytes:
    if not occurrences:
        return source
    sorted_occ = sorted(occurrences, key=lambda o: o.byte_start, reverse=True)
    new_source = source
    for occ in sorted_occ:
        new_source = (
            new_source[: occ.byte_start]
            + replacement.encode("utf-8")
            + new_source[occ.byte_end :]
        )
    return new_source


def remove_dead_assignment(
    source: bytes, target: Any, grammar: Grammar
) -> bytes | None:
    if target.type not in ("assignment", "augmented_assignment"):
        return None
    var_name = _extract_var_name(source, target)
    if var_name is None:
        return None
    if var_name.startswith("_"):
        return None
    tree = _parse_tree(source, grammar)
    if tree is None:
        return None
    if _is_used_after(var_name, target.end_byte, tree.root_node):
        return None
    return source[: target.start_byte] + source[target.end_byte :]


def _extract_var_name(source: bytes, node: Any) -> str | None:
    for child in node.children:
        if child.type == "identifier":
            return source[child.start_byte : child.end_byte].decode(
                "utf-8", errors="replace"
            )
    return None


def _parse_tree(source: bytes, grammar: Grammar) -> Any:
    try:
        parser = Parser()
        parser.language = grammar.language
        return parser.parse(source)
    except Exception:
        return None


def _is_used_after(name: str, after_byte: int, node: Any) -> bool:
    if node.type == "identifier" and node.start_byte >= after_byte:
        return _node_text(node) == name
    for child in node.children:
        if _is_used_after(name, after_byte, child):
            return True
    return False


def _node_text(node: Any) -> str:
    return node.text.decode("utf-8", errors="replace") if node.text else ""


def try_escape_transforms(
    source: bytes,
    grammar: Grammar,
    is_interesting: Any,
    max_attempts: int = 50,
) -> bytes:
    current = source
    attempts = 0
    while attempts < max_attempts:
        transformed = _apply_one_escape(current, grammar, is_interesting)
        if transformed is None or transformed == current:
            break
        current = transformed
        attempts += 1
    return current


def _apply_one_escape(
    source: bytes, grammar: Grammar, is_interesting: Any
) -> bytes | None:
    tree = _parse_tree(source, grammar)
    if tree is None:
        return None
    for node in _walk_nodes(tree.root_node):
        if node.type in ("binary_operator", "boolean_operator", "comparison_operator"):
            result = simplify_expression(source, node, grammar)
            if result is not None and result != source:
                if is_interesting(result):
                    return result
    for node in _walk_nodes(tree.root_node):
        if node.type in ("assignment", "augmented_assignment"):
            result = remove_dead_assignment(source, node, grammar)
            if result is not None and result != source:
                if is_interesting(result):
                    return result
    return None


def _walk_nodes(node: Any):
    yield node
    for child in node.children:
        yield from _walk_nodes(child)
