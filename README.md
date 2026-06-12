# theseus-ship

A pure Python implementation of the [Perses](https://doi.org/10.1145/3180155.3180236) syntax-guided test case reducer (Sun et al., ICSE 2018).

Reference implementation: [nnunley/bonsai](https://github.com/nnunley/bonsai) (Rust).

## What It Does

Given a failing test case and a program file that triggers a bug, theseus-ship reduces the file to the smallest possible program that still reproduces the failure — while guaranteeing syntactic validity at every step.

## How It Works

1. Parse the input file into a concrete syntax tree using [tree-sitter](https://tree-sitter.github.io/)
2. Systematically try to remove or simplify subtrees via a priority queue (largest first)
3. Each candidate reduction is validated by reparsing — only syntactically valid reductions proceed
4. Test each valid candidate against an "interestingness test" (any shell command that exits 0 when the bug is still present)
5. Repeat until no further reductions are possible

### Transforms

- **Delete** — remove a node entirely
- **Unwrap** — replace a node with one of its type-compatible children
- **Unify identifiers** — rename bindings to canonical short forms (requires scope data)
- **Dead definition removal** — delete unreferenced definitions (requires scope data)

### Key Properties

- All intermediate results are syntactically valid
- Largest subtrees tried first (maximum reduction per test)
- Test results cached (duplicate calls avoided)
- Handles inputs with pre-existing parse errors

## Installation

```bash
uv sync
uv add tree-sitter tree-sitter-python
```

> **Note:** These are the only runtime dependencies. No other Python packages should be installed.

## Usage

```bash
# Reduce a file, keeping only what triggers the interestingness test
uv run theseus-ship --test "grep -q 'error'" input.py

# With a custom test script
uv run theseus-ship --test "./check.sh" input.js

# Limit reduction time
uv run theseus-ship --test "./check.sh" --max-time 30m --max-tests 1000 input.py
```

## Development

```bash
uv run ruff check src/     # lint
uv run ruff format src/    # format
uv run ty check src/       # type check
```

## License

MIT
