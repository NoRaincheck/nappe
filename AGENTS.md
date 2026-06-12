# theseus-ship - Agent Instructions

## Project Overview

theseus-ship is a pure Python implementation of the Perses syntax-guided test case reducer, based on the Rust reference implementation [bonsai](https://github.com/nnunley/bonsai).

Given a failing test case and a program file that triggers a bug, theseus-ship reduces the file to the smallest possible program that still reproduces the failure — while guaranteeing syntactic validity at every step.

## Architecture

The project lives in `src/theseus_ship/` and is structured as a Python package using `uv` as the package manager.

```
src/theseus_ship/
├── cli.py        — argparse CLI, file I/O, language detection
├── grammar.py    — tree-sitter language loading, error-node detection
├── parser.py     — source parsing, CST walk, token counting
├── tree.py       — data types: NodeInfo, TransformCandidate, ParseResult
├── transforms.py — Delete/Unwrap transforms with reparse validation
├── reducer.py    — priority queue reduction loop, cache, interestingness test
└── scope.py      — stub for scope-aware transforms (Phase 5)
```

**Data flow:** file → parse → ParseResult → generate candidates → apply transform → reparse+validate → interestingness test → accept/reject → loop

## Dependencies

The only runtime dependencies are:

```bash
uv add tree-sitter tree-sitter-python
```

**Do NOT install any other Python packages.** If you need additional functionality, implement it using only the standard library and tree-sitter. If you believe another package is necessary, discuss it first.

## Development Workflow

### Lint & Format

```bash
uv run ruff check src/
uv run ruff format src/
```

### Type Checking

```bash
uv run ty check src/
```

### Run All Tests

```bash
uv run pytest tests/
```

### Run the CLI

```bash
uv run theseus-ship --test test_interesting.py::test_still_fails input.py
```

## Key Design Decisions

1. **Reparse is the definitive validity gate.** Always reparse after every candidate transformation and reject any result with new ERROR/MISSING nodes.
2. **Priority queue stores byte ranges, not node handles.** Node handles invalidate after reparse — use (byte_range, kind_id, token_count) tuples.
3. **Cache test results.** Hash the file content to avoid re-running the interestingness test on identical inputs.
4. **No shell interpolation.** Use `subprocess.run` with list arguments, never `shell=True`.

## Style Guide

### Linting & Formatting
- Use **ruff** for all linting and formatting. Run `uv run ruff check src/` and `uv run ruff format src/` before committing.

### Package Structure
- Keep `__init__.py` files **empty** — no imports, no code.

### Testing
- Add tests for all new functionality. Tests live in `tests/` and mirror the source structure.

### Typing
- Ensure code passes `uv run ty check src/` with no errors. Use type annotations for all public functions.

## Conventions & Patterns

- Reparse is the sole validity gate — never manipulate AST directly
- Priority queue stores byte ranges, not node handles (handles invalidate after reparse)
- Content-hash cache avoids re-running identical interestingness tests
- subprocess always uses `shell=False` — never `shell=True`
- All `__init__.py` files are empty
- Type annotations on all public functions
- Tests in `tests/` mirror source structure

## Reference Materials

- [Perses paper](https://doi.org/10.1109/ICSE.2018.00046) — algorithm specification
- [bonsai source](https://github.com/nnunley/bonsai) — Rust reference implementation
- [tree-sitter](https://tree-sitter.github.io/) — parsing library and grammar ecosystem

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
