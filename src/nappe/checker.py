from __future__ import annotations

from typing import Any

from nappe.grammar import Grammar
from nappe.parser import parse_source
from nappe.rules import RULES, Suggestion


def check_dead_functions(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    result = parse_source(source, grammar)
    suggestions: list[Suggestion] = []
    for node in result.all_nodes:
        if node.kind != "function_definition":
            continue
        name = _get_function_name(source, node)
        if name is None or name.startswith("_"):
            continue
        callers = _count_references(source, name, node.byte_end)
        if callers > 0:
            continue
        line, col = _byte_to_line_col(source, node.byte_start)
        new_source = source[: node.byte_start] + source[node.byte_end :]
        new_source = new_source.strip() + b"\n"
        ctx = _get_context_line(source, node.byte_start)
        suggestions.append(
            Suggestion(
                file_path=file_path,
                line=line,
                col=col,
                rule=RULES["RED100"],
                old_source=source,
                new_source=new_source,
                context=ctx,
            )
        )
    return suggestions


def check_dead_classes(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    result = parse_source(source, grammar)
    suggestions: list[Suggestion] = []
    for node in result.all_nodes:
        if node.kind != "class_definition":
            continue
        name = _get_class_name(source, node)
        if name is None or name.startswith("_"):
            continue
        refs = _count_references(source, name, node.byte_end)
        if refs > 0:
            continue
        line, col = _byte_to_line_col(source, node.byte_start)
        new_source = source[: node.byte_start] + source[node.byte_end :]
        new_source = new_source.strip() + b"\n"
        ctx = _get_context_line(source, node.byte_start)
        suggestions.append(
            Suggestion(
                file_path=file_path,
                line=line,
                col=col,
                rule=RULES["RED101"],
                old_source=source,
                new_source=new_source,
                context=ctx,
            )
        )
    return suggestions


def check_unused_assignments(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    result = parse_source(source, grammar)
    suggestions: list[Suggestion] = []
    for node in result.all_nodes:
        if node.kind not in ("assignment", "augmented_assignment"):
            continue
        var_name = _extract_var_name(source, node)
        if var_name is None or var_name.startswith("_"):
            continue
        if _is_used_after(var_name, node.byte_end, source):
            continue
        line, col = _byte_to_line_col(source, node.byte_start)
        new_source = source[: node.byte_start] + source[node.byte_end :]
        new_source = new_source.strip() + b"\n"
        ctx = _get_context_line(source, node.byte_start)
        suggestions.append(
            Suggestion(
                file_path=file_path,
                line=line,
                col=col,
                rule=RULES["RED102"],
                old_source=source,
                new_source=new_source,
                context=ctx,
            )
        )
    return suggestions


def check_constant_expressions(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    from nappe.escapes import _safe_eval

    result = parse_source(source, grammar)
    suggestions: list[Suggestion] = []
    for node in result.all_nodes:
        if node.kind not in (
            "binary_operator",
            "boolean_operator",
            "comparison_operator",
        ):
            continue
        text = source[node.byte_start : node.byte_end].decode("utf-8", errors="replace")
        evaled = _safe_eval(text.strip())
        if evaled is None:
            continue
        replacement = str(evaled).encode("utf-8")
        if replacement == source[node.byte_start : node.byte_end]:
            continue
        line, col = _byte_to_line_col(source, node.byte_start)
        new_source = source[: node.byte_start] + replacement + source[node.byte_end :]
        ctx = _get_context_line(source, node.byte_start)
        suggestions.append(
            Suggestion(
                file_path=file_path,
                line=line,
                col=col,
                rule=RULES["RED200"],
                old_source=source,
                new_source=new_source,
                context=ctx,
            )
        )
    return suggestions


def check_redundant_parens(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    result = parse_source(source, grammar)
    suggestions: list[Suggestion] = []
    for node in result.all_nodes:
        if node.kind != "parenthesized_expression":
            continue
        if len(node.child_kinds) != 3:
            continue
        if node.child_kinds[0] != "(" or node.child_kinds[2] != ")":
            continue
        inner_start = node.child_byte_starts[1]
        inner_end = node.child_byte_ends[1]
        inner = source[inner_start:inner_end]
        text = source[node.byte_start : node.byte_end]
        if text == inner:
            continue
        line, col = _byte_to_line_col(source, node.byte_start)
        new_source = source[: node.byte_start] + inner + source[node.byte_end :]
        ctx = _get_context_line(source, node.byte_start)
        suggestions.append(
            Suggestion(
                file_path=file_path,
                line=line,
                col=col,
                rule=RULES["RED201"],
                old_source=source,
                new_source=new_source,
                context=ctx,
            )
        )
    return suggestions


def check_unnecessary_semicolons(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    lines = source.split(b"\n")
    offset = 0
    for i, line_bytes in enumerate(lines):
        stripped = line_bytes.rstrip()
        if stripped.endswith(b";"):
            new_line = stripped[:-1]
            new_source = (
                source[:offset]
                + new_line
                + b"\n"
                + source[offset + len(line_bytes) + 1 :]
            )
            line_num = i + 1
            col = len(line_bytes.rstrip()) - 1
            ctx = line_bytes.decode("utf-8", errors="replace")
            suggestions.append(
                Suggestion(
                    file_path=file_path,
                    line=line_num,
                    col=col,
                    rule=RULES["RED202"],
                    old_source=source,
                    new_source=new_source,
                    context=ctx,
                )
            )
        offset += len(line_bytes) + 1
    return suggestions


def check_trailing_whitespace(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    lines = source.split(b"\n")
    offset = 0
    for i, line_bytes in enumerate(lines):
        if line_bytes != line_bytes.rstrip():
            new_line = line_bytes.rstrip()
            new_source = source[:offset] + new_line + source[offset + len(line_bytes) :]
            line_num = i + 1
            col = len(line_bytes.rstrip())
            ctx = line_bytes.decode("utf-8", errors="replace")
            suggestions.append(
                Suggestion(
                    file_path=file_path,
                    line=line_num,
                    col=col,
                    rule=RULES["RED203"],
                    old_source=source,
                    new_source=new_source,
                    context=ctx,
                )
            )
        offset += len(line_bytes) + 1
    return suggestions


def check_redundant_newlines(
    source: bytes, grammar: Grammar, file_path: str
) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    if source.endswith(b"\n\n"):
        new_source = source.rstrip(b"\n") + b"\n"
        if new_source != source:
            line_num = source.count(b"\n") + 1
            ctx = ""
            suggestions.append(
                Suggestion(
                    file_path=file_path,
                    line=line_num,
                    col=0,
                    rule=RULES["RED204"],
                    old_source=source,
                    new_source=new_source,
                    context=ctx,
                )
            )
    return suggestions


ALL_CHECKS = [
    check_trailing_whitespace,
    check_redundant_newlines,
    check_unnecessary_semicolons,
    check_redundant_parens,
    check_constant_expressions,
    check_unused_assignments,
    check_dead_functions,
    check_dead_classes,
]


def _get_function_name(source: bytes, node: Any) -> str | None:
    for i, kind in enumerate(node.child_kinds):
        if kind == "identifier":
            start = node.child_byte_starts[i]
            end = node.child_byte_ends[i]
            return source[start:end].decode("utf-8", errors="replace")
    return None


def _get_class_name(source: bytes, node: Any) -> str | None:
    for i, kind in enumerate(node.child_kinds):
        if kind == "identifier":
            start = node.child_byte_starts[i]
            end = node.child_byte_ends[i]
            return source[start:end].decode("utf-8", errors="replace")
    return None


def _extract_var_name(source: bytes, node: Any) -> str | None:
    for i, kind in enumerate(node.child_kinds):
        if kind == "identifier":
            start = node.child_byte_starts[i]
            end = node.child_byte_ends[i]
            return source[start:end].decode("utf-8", errors="replace")
    return None


def _count_references(source: bytes, name: str, after_byte: int) -> int:
    text = source.decode("utf-8", errors="replace")
    count = 0
    search_from = 0
    while True:
        idx = text.find(name, search_from)
        if idx == -1:
            break
        byte_idx = len(text[:idx].encode("utf-8", errors="replace"))
        if byte_idx >= after_byte:
            before = text[max(0, idx - 1) : idx]
            after = text[idx + len(name) : idx + len(name) + 1]
            if (not before or not before.isalnum()) and (
                not after or not after.isalnum()
            ):
                count += 1
        search_from = idx + 1
    return count


def _is_used_after(name: str, after_byte: int, source: bytes) -> bool:
    text = source.decode("utf-8", errors="replace")
    search_from = 0
    while True:
        idx = text.find(name, search_from)
        if idx == -1:
            break
        byte_idx = len(text[:idx].encode("utf-8", errors="replace"))
        if byte_idx >= after_byte:
            before = text[max(0, idx - 1) : idx]
            after = text[idx + len(name) : idx + len(name) + 1]
            if (not before or not before.isalnum()) and (
                not after or not after.isalnum()
            ):
                return True
        search_from = idx + 1
    return False


def _byte_to_line_col(source: bytes, byte_offset: int) -> tuple[int, int]:
    before = source[:byte_offset]
    line = before.count(b"\n") + 1
    last_nl = before.rfind(b"\n")
    col = byte_offset - (last_nl + 1) if last_nl >= 0 else byte_offset
    return line, col + 1


def _get_context_line(source: bytes, byte_offset: int) -> str:
    last_nl = source.rfind(b"\n", 0, byte_offset)
    next_nl = source.find(b"\n", byte_offset)
    if next_nl == -1:
        next_nl = len(source)
    start = last_nl + 1 if last_nl >= 0 else 0
    return source[start:next_nl].decode("utf-8", errors="replace")
