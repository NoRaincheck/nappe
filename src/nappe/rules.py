from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FixSafety(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"


@dataclass(frozen=True)
class Rule:
    code: str
    description: str
    safety: FixSafety


@dataclass
class Suggestion:
    file_path: str
    line: int
    col: int
    rule: Rule
    old_source: bytes
    new_source: bytes
    context: str


RULES: dict[str, Rule] = {
    "RED100": Rule("RED100", "Dead function (no callers)", FixSafety.UNSAFE),
    "RED101": Rule("RED101", "Dead class (no instantiations)", FixSafety.UNSAFE),
    "RED102": Rule("RED102", "Unused variable assignment", FixSafety.UNSAFE),
    "RED200": Rule("RED200", "Constant expression simplification", FixSafety.SAFE),
    "RED201": Rule("RED201", "Redundant parentheses", FixSafety.SAFE),
    "RED202": Rule("RED202", "Unnecessary semicolon", FixSafety.SAFE),
    "RED203": Rule("RED203", "Trailing whitespace", FixSafety.SAFE),
    "RED204": Rule("RED204", "Redundant newline", FixSafety.SAFE),
}
