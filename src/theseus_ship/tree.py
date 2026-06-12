from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TransformKind(Enum):
    DELETE = "delete"
    UNWRAP = "unwrap"


@dataclass(frozen=True)
class NodeInfo:
    """Immutable snapshot of a tree-sitter node's identity."""

    kind: str
    byte_start: int
    byte_end: int
    token_count: int
    has_errors: bool
    child_kinds: tuple[str, ...]


@dataclass(frozen=True)
class TransformCandidate:
    """A candidate transformation to try."""

    target: NodeInfo
    kind: TransformKind
    unwrap_child_index: int | None = None


@dataclass
class ParseResult:
    """Result of parsing a source file."""

    source_bytes: bytes
    root_node: NodeInfo
    all_nodes: list[NodeInfo]
    error_node_count: int
