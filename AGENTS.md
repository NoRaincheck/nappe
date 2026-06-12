# unfluff - Agent Instructions

## Project Overview

unfluff is a syntax-guided test case reducer implementing the Perses
algorithm, based on the Rust reference implementation
[bonsai](https://github.com/nnunley/bonsai).

Given a failing test case and a program file that triggers a bug, unfluff
reduces the file to the smallest possible program that still reproduces the
failure — while guaranteeing syntactic validity at every step.

## Architecture

### Rust (primary)

The Rust implementation lives in `src/` and is built with `cargo`.

```
src/
├── bin/unfluff/main.rs — CLI entry point
├── lib.rs                   — library root
├── cache.rs                 — content-hash caching
├── checker.rs               — static analysis checks
├── diff.rs                  — diff/fix application
├── escapes.rs               — string escape handling
├── grammar.rs               — tree-sitter language loading
├── parser.rs                — source parsing, CST walk
├── reducer.rs               — priority queue reduction loop
├── rules.rs                 — check rule definitions
├── shrink.rs                — shrinkray-compatible interface
├── token_reduce.rs          — token-level reduction
├── transforms.rs            — Delete/Unwrap transforms
├── tree.rs                  — data types
└── util.rs                  — utilities
```

**Data flow:** file → parse → CST → generate candidates → apply transform →
reparse+validate → interestingness test → accept/reject → loop

### Python (reference)

The Python implementation lives in `src/theseus_ship/` and is kept for
comparison and as a reference for the algorithm. Accessible via the `--legacy`
flag.

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

## Dependencies

### Rust

Runtime dependencies in `Cargo.toml`:

```toml
tree-sitter = "0.25"
tree-sitter-language = "0.1"
tree-sitter-python = "0.25"
tree-sitter-javascript = "0.25"
tree-sitter-typescript = "0.23"
tree-sitter-rust = "0.24"
tree-sitter-go = "0.25"
tree-sitter-c = "0.24"
tree-sitter-cpp = "0.23"
clap = { version = "4", features = ["derive"] }
blake3 = "1"
tempfile = "3"
glob = "0.3"
```

### Python (reference)

```bash
uv add tree-sitter tree-sitter-python
```

**Do NOT install any other Python packages.** If you need additional
functionality, implement it using only the standard library and tree-sitter. If
you believe another package is necessary, discuss it first.

## Development Workflow

### Rust (primary)

```bash
cargo build --release      # build
cargo test                 # test
cargo clippy               # lint
cargo fmt                  # format
```

### Python (reference)

```bash
uv run ruff check src/theseus_ship/
uv run ruff format src/theseus_ship/
uv run ty check src/theseus_ship/
uv run pytest tests/
```

### Run the CLI

```bash
# Rust (default)
cargo run -- reduce --test test_interesting.py::test_still_fails input.py

# Python (legacy)
cargo run -- --legacy reduce --test test_interesting.py::test_still_fails input.py
```

## Key Design Decisions

1. **Rust is the primary implementation.** All new features and optimizations
   should target Rust first. Python is maintained for reference only.
2. **Reparse is the definitive validity gate.** Always reparse after every
   candidate transformation and reject any result with new ERROR/MISSING nodes.
3. **Priority queue stores byte ranges, not node handles.** Node handles
   invalidate after reparse — use (byte_range, kind_id, token_count) tuples.
4. **Cache test results.** Hash the file content to avoid re-running the
   interestingness test on identical inputs.
5. **No shell interpolation.** Use `subprocess.run` with list arguments, never
   `shell=True` (Python reference).

## Style Guide

### Rust

- Use `cargo fmt` for formatting
- Use `cargo clippy` for linting
- Follow standard Rust conventions (snake_case, camelCase for types)

### Python (reference)

- Use **ruff** for all linting and formatting
- Keep `__init__.py` files **empty** — no imports, no code
- Type annotations on all public functions
- Tests in `tests/` mirror source structure

## Conventions & Patterns

- Reparse is the sole validity gate — never manipulate AST directly
- Priority queue stores byte ranges, not node handles (handles invalidate after
  reparse)
- Content-hash cache avoids re-running identical interestingness tests
- subprocess always uses `shell=False` — never `shell=True`
- All `__init__.py` files are empty
- Type annotations on all public functions
- Tests in `tests/` mirror source structure

## Reference Materials

- [Perses paper](https://doi.org/10.1109/ICSE.2018.00046) — algorithm
  specification
- [bonsai source](https://github.com/nnunley/bonsai) — Rust reference
  implementation
- [tree-sitter](https://tree-sitter.github.io/) — parsing library and grammar
  ecosystem

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->

## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full
workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown
  TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses
`refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export.
See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for
details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT
complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs
   follow-up
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
