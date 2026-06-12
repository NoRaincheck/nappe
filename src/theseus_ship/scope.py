from __future__ import annotations

from dataclasses import dataclass

from theseus_ship.tree import NodeInfo


@dataclass
class ScopeData:
    bindings: dict[str, list[NodeInfo]]
    references: dict[str, list[NodeInfo]]


def load_scope(query_path: str) -> ScopeData:
    raise NotImplementedError("Scope queries not yet implemented")


def find_dead_definitions(source: bytes, scope: ScopeData) -> list[NodeInfo]:
    return []


def unify_identifiers(source: bytes, scope: ScopeData) -> dict[str, str]:
    return {}
