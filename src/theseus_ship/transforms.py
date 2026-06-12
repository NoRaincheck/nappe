from __future__ import annotations

from theseus_ship.grammar import Grammar
from theseus_ship.parser import parse_source
from theseus_ship.tree import NodeInfo, ParseResult, TransformCandidate, TransformKind


def generate_candidates(
    result: ParseResult, grammar: Grammar
) -> list[TransformCandidate]:
    candidates: list[TransformCandidate] = []
    root = result.root_node

    for node in result.all_nodes:
        if node.byte_start == root.byte_start and node.byte_end == root.byte_end:
            continue

        if not node.has_errors:
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
                        )
                    )

    return candidates


def apply_delete(source: bytes, target: NodeInfo) -> bytes:
    return source[: target.byte_start] + source[target.byte_end :]


def apply_unwrap(source: bytes, target: NodeInfo, child: NodeInfo) -> bytes:
    return (
        source[: target.byte_start]
        + source[child.byte_start : child.byte_end]
        + source[target.byte_end :]
    )


def apply_transform(
    source: bytes,
    candidate: TransformCandidate,
    grammar: Grammar,
    root_node: NodeInfo | None = None,
) -> tuple[bytes, ParseResult] | None:
    target = candidate.target

    if root_node is not None:
        if (
            target.byte_start == root_node.byte_start
            and target.byte_end == root_node.byte_end
        ):
            return None

    if candidate.kind == TransformKind.DELETE:
        new_source = apply_delete(source, target)
    elif candidate.kind == TransformKind.UNWRAP:
        if candidate.unwrap_child_index is None:
            return None
        if candidate.unwrap_child_index >= len(target.child_kinds):
            return None
        child = NodeInfo(
            kind=target.child_kinds[candidate.unwrap_child_index],
            byte_start=0,
            byte_end=0,
            token_count=0,
            has_errors=False,
            child_kinds=(),
        )
        new_source = apply_unwrap(source, target, child)
    else:
        return None

    if new_source == source:
        return None

    if not new_source.strip():
        return None

    new_result = parse_source(new_source, grammar)

    if new_result.error_node_count > result_error_count(source, grammar):
        return None

    return new_source, new_result


def result_error_count(source: bytes, grammar: Grammar) -> int:
    result = parse_source(source, grammar)
    return result.error_node_count
