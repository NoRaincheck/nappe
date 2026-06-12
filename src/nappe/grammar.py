from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Language

_ERROR_KINDS: frozenset[str] = frozenset({"ERROR", "MISSING", "UNEXPECTED_TOKEN"})
_PROTECTED_KINDS: frozenset[str] = frozenset({"comment"})
_KEYWORD_KINDS: frozenset[str] = frozenset(
    {
        "def",
        "class",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "return",
        "import",
        "from",
        "as",
        "lambda",
        "yield",
        "assert",
        "del",
        "raise",
        "pass",
        "break",
        "continue",
        "global",
        "nonlocal",
        "async",
        "await",
        "match",
        "case",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        ",",
        ":",
        ";",
        ".",
        "->",
        "=",
        "+=",
        "-=",
        "*=",
        "/=",
        "//=",
        "%=",
        "**=",
        ">>=",
        "<<=",
        "&=",
        "^=",
        "|=",
        "and",
        "or",
        "not",
        "in",
        "is",
        "is not",
        "not in",
    }
)


class Grammar:
    """Wraps a tree-sitter language with helper methods."""

    def __init__(
        self, lang_module: Any, name: str = "python", lang_func: Any = None
    ) -> None:
        if lang_func is not None:
            self._language = Language(lang_func())
        else:
            self._language = Language(lang_module.language())
        self._name = name
        self._field_cache: dict[tuple[str, int], str] = {}
        self._build_field_cache()

    @property
    def language(self) -> Language:
        return self._language

    @property
    def name(self) -> str:
        return self._name

    def is_error_node(self, kind: str) -> bool:
        return kind in _ERROR_KINDS

    def is_protected_node(self, kind: str) -> bool:
        return kind in _PROTECTED_KINDS

    def unwrap_compatible_kinds(self, node_kind: str) -> frozenset[str]:
        return self.subtypes(node_kind)

    def subtypes(self, kind: str) -> frozenset[str]:
        kind_id = self._language.id_for_node_kind(kind, True)
        if kind_id is None:
            return frozenset({kind})
        result: set[str] = {kind}
        worklist = [kind_id]
        seen_ids: set[int] = set()
        while worklist:
            current_id = worklist.pop()
            if current_id in seen_ids:
                continue
            seen_ids.add(current_id)
            subtype_ids = self._language.subtypes(current_id)
            for sid in subtype_ids:
                name = self._language.node_kind_for_id(sid)
                if name is not None and name not in result:
                    result.add(name)
                    worklist.append(sid)
        return frozenset(result)

    def supertypes(self, kind: str) -> frozenset[str]:
        kind_id = self._language.id_for_node_kind(kind, True)
        if kind_id is None:
            return frozenset({kind})
        sup_ids = self._language.supertypes
        result: set[str] = {kind}
        for sid in sup_ids:
            sub_ids = self._language.subtypes(sid)
            for sub_id in sub_ids:
                if sub_id == kind_id:
                    name = self._language.node_kind_for_id(sid)
                    if name is not None:
                        result.add(name)
        return frozenset(result)

    def is_kleene_node(self, node_kind: str, child_kinds: tuple[str, ...]) -> bool:
        named = [k for k in child_kinds if k not in _KEYWORD_KINDS]
        return len(named) >= 2 and len(set(named)) == 1

    def is_subtype(self, child_kind: str, parent_kind: str) -> bool:
        return child_kind in self.subtypes(parent_kind)

    def field_name_for_child(self, parent_kind: str, child_index: int) -> str | None:
        return self._field_cache.get((parent_kind, child_index))

    def _build_field_cache(self) -> None:
        from tree_sitter import Parser

        parser = Parser(self._language)
        sample = (
            b"def f(x, y=1):\n"
            b"    return x + y\n"
            b"if True:\n"
            b"    x = 1\n"
            b"class C:\n"
            b"    def m(self): pass\n"
            b"x = [1]\n"
            b"y = {1: 2}\n"
            b"z = (1,)\n"
            b"for i in x:\n"
            b"    pass\n"
            b"while True:\n"
            b"    break\n"
        )
        tree = parser.parse(sample)

        def _walk(node: object) -> None:
            from tree_sitter import Node as TSNode

            assert isinstance(node, TSNode)
            for i, child in enumerate(node.children):
                fname = node.field_name_for_child(i)
                if fname is not None:
                    self._field_cache[(node.type, i)] = fname
            for child in node.children:
                _walk(child)

        _walk(tree.root_node)


_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
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
    if lang_name == "javascript":
        import tree_sitter_javascript

        return Grammar(tree_sitter_javascript, name="javascript")
    if lang_name == "typescript":
        import tree_sitter_typescript

        return Grammar(
            tree_sitter_typescript,
            name="typescript",
            lang_func=tree_sitter_typescript.language_typescript,
        )
    if lang_name == "rust":
        import tree_sitter_rust

        return Grammar(tree_sitter_rust, name="rust")
    if lang_name == "go":
        import tree_sitter_go

        return Grammar(tree_sitter_go, name="go")
    if lang_name == "c":
        import tree_sitter_c

        return Grammar(tree_sitter_c, name="c")
    if lang_name == "cpp":
        import tree_sitter_cpp

        return Grammar(tree_sitter_cpp, name="cpp")
    msg = f"Unsupported language: {lang_name}"
    raise ValueError(msg)
