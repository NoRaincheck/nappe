from __future__ import annotations

from typing import Callable

from nappe.grammar import Grammar
from nappe.parser import parse_source


def _strip_trailing_whitespace(source: bytes) -> bytes | None:
    lines = source.split(b"\n")
    new_lines = [line.rstrip() for line in lines]
    new_source = b"\n".join(new_lines)
    if new_source == source:
        return None
    return new_source


def _strip_trailing_newlines(source: bytes) -> bytes | None:
    if not source.endswith(b"\n"):
        return None
    stripped = source.rstrip(b"\n") + b"\n"
    if stripped == source:
        return None
    return stripped


def _remove_unnecessary_semicolons(
    source: bytes, grammar: Grammar
) -> tuple[bytes, bytes] | None:
    result = parse_source(source, grammar)
    changed = False
    new_source = source
    for node in reversed(result.all_nodes):
        if node.kind == ";" and not node.has_errors:
            candidate = new_source[: node.byte_start] + new_source[node.byte_end :]
            if candidate.strip():
                reparse = parse_source(candidate, grammar)
                if reparse.error_node_count == 0:
                    new_source = candidate
                    changed = True
    if not changed:
        return None
    return source, new_source


def _remove_redundant_parens(source: bytes, grammar: Grammar) -> bytes | None:
    result = parse_source(source, grammar)
    for node in reversed(result.all_nodes):
        if node.kind != "parenthesized_expression":
            continue
        if node.has_errors:
            continue
        if len(node.child_kinds) != 3:
            continue
        if node.child_kinds[0] != "(" or node.child_kinds[2] != ")":
            continue
        inner_start = node.child_byte_starts[1]
        inner_end = node.child_byte_ends[1]
        candidate = (
            source[: node.byte_start]
            + source[inner_start:inner_end]
            + source[node.byte_end :]
        )
        if candidate.strip():
            reparse = parse_source(candidate, grammar)
            if reparse.error_node_count <= result.error_node_count:
                source = candidate
    return source


def token_reduce(
    source: bytes,
    grammar: Grammar,
    is_interesting: Callable[[bytes], bool],
) -> bytes:
    current = source

    step = _strip_trailing_whitespace(current)
    if step is not None:
        reparsed = parse_source(step, grammar)
        if reparsed.error_node_count == 0 and is_interesting(step):
            current = step

    step = _strip_trailing_newlines(current)
    if step is not None:
        reparsed = parse_source(step, grammar)
        if reparsed.error_node_count == 0 and is_interesting(step):
            current = step

    step = _remove_redundant_parens(current, grammar)
    if step is not None and step != current:
        reparsed = parse_source(step, grammar)
        if reparsed.error_node_count == 0 and is_interesting(step):
            current = step

    result = _remove_unnecessary_semicolons(current, grammar)
    if result is not None:
        _, new_source = result
        if new_source != current:
            reparsed = parse_source(new_source, grammar)
            if reparsed.error_node_count == 0 and is_interesting(new_source):
                current = new_source

    for _ in range(3):
        prev = current

        step = _strip_trailing_whitespace(current)
        if step is not None:
            reparsed = parse_source(step, grammar)
            if reparsed.error_node_count == 0 and is_interesting(step):
                current = step

        step = _strip_trailing_newlines(current)
        if step is not None:
            reparsed = parse_source(step, grammar)
            if reparsed.error_node_count == 0 and is_interesting(step):
                current = step

        if current == prev:
            break

    return current
