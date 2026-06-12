from __future__ import annotations

import json
from typing import Sequence

from nappe.rules import FixSafety, Suggestion


def format_text(suggestions: Sequence[Suggestion]) -> str:
    if not suggestions:
        return ""
    lines: list[str] = []
    for s in suggestions:
        lines.append(
            f"{s.file_path}:{s.line}:{s.col}: {s.rule.code} {s.rule.description}"
        )
        if s.context:
            lines.append(f"    {s.line} | {s.context}")
            marker = " " * (len(str(s.line)) + 4) + "^" * len(s.context.strip())
            lines.append(f"{marker} {s.rule.code}")
        lines.append("")
    safe = sum(1 for s in suggestions if s.rule.safety == FixSafety.SAFE)
    unsafe = sum(1 for s in suggestions if s.rule.safety == FixSafety.UNSAFE)
    lines.append(
        f"Found {len(suggestions)} issue{'s' if len(suggestions) != 1 else ''} ({safe} safe, {unsafe} unsafe)."
    )
    return "\n".join(lines)


def format_diff(suggestions: Sequence[Suggestion]) -> str:
    if not suggestions:
        return ""
    lines: list[str] = []
    for s in suggestions:
        lines.append(f"--- a/{s.file_path}")
        lines.append(f"+++ b/{s.file_path}")
        lines.append(f"@@ -{s.line},1 +{s.line},1 @@")
        old_line = s.context
        new_lines = s.new_source.decode("utf-8", errors="replace").split("\n")
        new_line = new_lines[0] if new_lines else ""
        lines.append(f"-{old_line}")
        lines.append(f"+{new_line}")
        lines.append("")
    return "\n".join(lines)


def format_json(suggestions: Sequence[Suggestion]) -> str:
    data = []
    for s in suggestions:
        data.append(
            {
                "file": s.file_path,
                "line": s.line,
                "col": s.col,
                "code": s.rule.code,
                "message": s.rule.description,
                "safety": s.rule.safety.value,
            }
        )
    return json.dumps(data, indent=2)


def apply_fixes(
    suggestions: Sequence[Suggestion], safety: FixSafety
) -> dict[str, bytes]:
    by_file: dict[str, list[Suggestion]] = {}
    for s in suggestions:
        if s.rule.safety == safety:
            by_file.setdefault(s.file_path, []).append(s)
    results: dict[str, bytes] = {}
    for file_path, file_suggestions in by_file.items():
        source = file_suggestions[0].old_source
        for s in sorted(file_suggestions, key=lambda x: x.line, reverse=True):
            source = s.new_source
        results[file_path] = source
    return results
