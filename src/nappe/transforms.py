from __future__ import annotations

from collections import deque
from typing import Callable

from nappe.grammar import Grammar, _KEYWORD_KINDS
from nappe.parser import parse_source, reparse_source
from nappe.tree import NodeInfo, ParseResult, TransformCandidate, TransformKind


def bounded_bfs(
    source: bytes,
    root_node: NodeInfo,
    target: NodeInfo,
    grammar: Grammar,
    predicate: Callable[[NodeInfo], bool],
    max_depth: int = 4,
) -> list[TransformCandidate]:
    target_supers = grammar.supertypes(target.kind)
    queue: deque[tuple[int, NodeInfo]] = deque()
    for idx, child_kind in enumerate(target.child_kinds):
        child = NodeInfo(
            kind=child_kind,
            byte_start=target.child_byte_starts[idx],
            byte_end=target.child_byte_ends[idx],
            token_count=0,
            has_errors=False,
            child_kinds=(),
        )
        queue.append((1, child))

    found: list[TransformCandidate] = []
    while queue:
        depth, node = queue.popleft()
        if depth > max_depth:
            continue
        if predicate(node):
            node_supers = grammar.supertypes(node.kind)
            if node_supers & target_supers:
                found.append(
                    TransformCandidate(
                        target=target,
                        kind=TransformKind.UNWRAP,
                        unwrap_child_index=-1,
                        child_byte_start=node.byte_start,
                        child_byte_end=node.byte_end,
                    )
                )
        for idx, child_kind in enumerate(node.child_kinds):
            child = NodeInfo(
                kind=child_kind,
                byte_start=node.child_byte_starts[idx],
                byte_end=node.child_byte_ends[idx],
                token_count=0,
                has_errors=False,
                child_kinds=(),
            )
            queue.append((depth + 1, child))

    found.sort(key=lambda c: c.target.token_count, reverse=True)
    return found


def generate_candidates(
    result: ParseResult, grammar: Grammar
) -> list[TransformCandidate]:
    candidates: list[TransformCandidate] = []
    root = result.root_node

    for node in result.all_nodes:
        if node.byte_start == root.byte_start and node.byte_end == root.byte_end:
            continue

        if not node.has_errors and not grammar.is_protected_node(node.kind):
            if grammar.is_kleene_node(node.kind, node.child_kinds):
                candidates.append(
                    TransformCandidate(target=node, kind=TransformKind.DDMIN)
                )
            else:
                candidates.append(
                    TransformCandidate(target=node, kind=TransformKind.DELETE)
                )

        if node.child_kinds:
            compatible = grammar.unwrap_compatible_kinds(node.kind)
            for idx, child_kind in enumerate(node.child_kinds):
                if child_kind in compatible:
                    candidates.append(
                        TransformCandidate(
                            target=node,
                            kind=TransformKind.UNWRAP,
                            unwrap_child_index=idx,
                            child_byte_start=node.child_byte_starts[idx],
                            child_byte_end=node.child_byte_ends[idx],
                        )
                    )

            bfs = bounded_bfs(
                result.source_bytes,
                root,
                node,
                grammar,
                lambda n: not n.has_errors and not grammar.is_protected_node(n.kind),
            )
            candidates.extend(bfs)

    return candidates


def apply_delete(source: bytes, target: NodeInfo) -> bytes:
    return source[: target.byte_start] + source[target.byte_end :]


def apply_unwrap(
    source: bytes, target: NodeInfo, child_byte_start: int, child_byte_end: int
) -> bytes:
    return (
        source[: target.byte_start]
        + source[child_byte_start:child_byte_end]
        + source[target.byte_end :]
    )


def apply_ddmin(
    source: bytes,
    target: NodeInfo,
    grammar: Grammar,
    is_interesting: Callable[[bytes], bool],
    base_error_count: int | None = None,
    strict: bool = False,
) -> tuple[bytes, ParseResult] | None:
    named_children = [
        (i, target.child_byte_starts[i], target.child_byte_ends[i])
        for i, kind in enumerate(target.child_kinds)
        if kind not in _KEYWORD_KINDS
    ]
    if len(named_children) < 2:
        return None

    removable = list(range(len(named_children)))

    def ddmin(elems: list[int]) -> list[int]:
        if len(elems) <= 1:
            return elems
        n = 2
        while n <= len(elems):
            chunk_size = max(1, len(elems) // n)
            for i in range(0, len(elems), chunk_size):
                partition = elems[i : i + chunk_size]
                complement = [e for e in elems if e not in partition]
                if not complement:
                    continue
                new_source = _remove_children(
                    source, target, complement, named_children
                )
                if new_source == source or not new_source.strip():
                    continue
                if _check_valid(new_source, grammar, base_error_count, strict):
                    if is_interesting(new_source):
                        return ddmin(complement)
            n *= 2
        return elems

    remaining = ddmin(removable)
    if len(remaining) == len(named_children):
        return None

    new_source = _remove_children(source, target, remaining, named_children)
    if new_source == source or not new_source.strip():
        return None
    if not _check_valid(new_source, grammar, base_error_count, strict):
        return None
    new_result = parse_source(new_source, grammar)
    return new_source, new_result


def _remove_children(
    source: bytes,
    target: NodeInfo,
    keep_indices: list[int],
    named_children: list[tuple[int, int, int]],
) -> bytes:
    remove_ranges = []
    for idx, start, end in named_children:
        if idx not in keep_indices:
            remove_ranges.append((start, end))
    remove_ranges.sort(reverse=True)
    new_source = source
    for start, end in remove_ranges:
        new_source = new_source[:start] + new_source[end:]
    return new_source


def _check_valid(
    source: bytes,
    grammar: Grammar,
    base_error_count: int | None,
    strict: bool,
) -> bool:
    result = parse_source(source, grammar)
    if base_error_count is None:
        base_error_count = result_error_count(source, grammar)
    if strict:
        return result.error_node_count == 0
    return result.error_node_count <= base_error_count


def apply_transform(
    source: bytes,
    candidate: TransformCandidate,
    grammar: Grammar,
    root_node: NodeInfo | None = None,
    base_error_count: int | None = None,
    old_result: ParseResult | None = None,
    strict: bool = False,
    is_interesting: Callable[[bytes], bool] | None = None,
) -> tuple[bytes, ParseResult] | None:
    target = candidate.target

    if root_node is not None:
        if (
            target.byte_start == root_node.byte_start
            and target.byte_end == root_node.byte_end
        ):
            return None

    if target.byte_start == target.byte_end:
        return None

    if candidate.kind == TransformKind.DELETE:
        new_source = apply_delete(source, target)
    elif candidate.kind == TransformKind.UNWRAP:
        if candidate.unwrap_child_index is None:
            return None
        if candidate.unwrap_child_index >= 0:
            if candidate.unwrap_child_index >= len(target.child_kinds):
                return None
        new_source = apply_unwrap(
            source, target, candidate.child_byte_start, candidate.child_byte_end
        )
    elif candidate.kind == TransformKind.DDMIN:
        if is_interesting is None:
            return None
        return apply_ddmin(
            source, target, grammar, is_interesting, base_error_count, strict
        )
    else:
        return None

    if new_source == source:
        return None

    if not new_source.strip():
        return None

    if old_result is not None:
        new_result = reparse_source(new_source, old_result, grammar)
    else:
        new_result = parse_source(new_source, grammar)

    if base_error_count is None:
        base_error_count = result_error_count(source, grammar)
    if strict:
        if new_result.error_node_count > 0:
            return None
    elif new_result.error_node_count > base_error_count:
        return None

    return new_source, new_result


def result_error_count(source: bytes, grammar: Grammar) -> int:
    result = parse_source(source, grammar)
    return result.error_node_count
