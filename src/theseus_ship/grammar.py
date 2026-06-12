from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Language

_ERROR_KINDS: frozenset[str] = frozenset({"ERROR", "MISSING", "UNEXPECTED_TOKEN"})


class Grammar:
    """Wraps a tree-sitter language with helper methods."""

    def __init__(self, lang_module: Any, name: str = "python") -> None:
        self._language = Language(lang_module.language())
        self._name = name

    @property
    def language(self) -> Language:
        return self._language

    @property
    def name(self) -> str:
        return self._name

    def is_error_node(self, kind: str) -> bool:
        return kind in _ERROR_KINDS

    def unwrap_compatible_kinds(self, node_kind: str) -> frozenset[str]:
        return frozenset({node_kind})


_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
}


def detect_language(path: str) -> str:
    ext = Path(path).suffix
    lang = _EXTENSION_MAP.get(ext)
    if lang is None:
        msg = f"Cannot detect language from extension '{ext}'"
        raise ValueError(msg)
    return lang


def load_grammar(lang_name: str) -> Grammar:
    if lang_name == "python":
        import tree_sitter_python

        return Grammar(tree_sitter_python, name="python")
    msg = f"Unsupported language: {lang_name}"
    raise ValueError(msg)
