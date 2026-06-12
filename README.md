# unfluff

A syntax-guided test case reducer implementing the
[Perses](https://doi.org/10.1145/3180155.3180236) algorithm (Sun et al., ICSE 2018).

Reference implementation: [nnunley/bonsai](https://github.com/nnunley/bonsai)
(Rust).

## What It Does

Given a failing test case and a program file that triggers a bug, unfluff
reduces the file to the smallest possible program that still reproduces the
failure — while guaranteeing syntactic validity at every step.

It also provides a `check` command for static analysis of source files,
detecting reducible patterns like dead code, unused assignments, and style
issues.

## How It Works

1. Parse the input file into a concrete syntax tree using
   [tree-sitter](https://tree-sitter.github.io/)
2. Systematically try to remove or simplify subtrees via a priority queue
   (largest first)
3. Each candidate reduction is validated by reparsing — only syntactically valid
   reductions proceed
4. Test each valid candidate against an "interestingness test" (any shell
   command that exits 0 when the bug is still present)
5. Repeat until no further reductions are possible

### Transforms

- **Delete** — remove a node entirely
- **Unwrap** — replace a node with one of its type-compatible children
- **Unify identifiers** — rename bindings to canonical short forms _(planned:
  requires scope data)_
- **Dead definition removal** — delete unreferenced definitions _(planned:
  requires scope data)_

### Key Properties

- All intermediate results are syntactically valid
- Largest subtrees tried first (maximum reduction per test)
- Test results cached (duplicate calls avoided)
- Handles inputs with pre-existing parse errors

## Supported Languages

Python, JavaScript, TypeScript, Rust, Go, C, C++ (via tree-sitter grammars).

## Implementation

The project has two implementations:

- **Rust** (primary) — native implementation in `src/`, built with `cargo`. This
  is the default and recommended implementation.
- **Python** (reference) — pure Python implementation in `src/theseus_ship/`,
  kept for comparison and as a reference for the algorithm. Accessible via the
  `--legacy` flag.

### Why Rust?

The Rust implementation provides significantly better performance for large
files and complex reduction scenarios, while maintaining full feature parity
with the Python reference.

## Installation

### Rust (recommended)

```bash
cargo build --release
cp target/release/unfluff ~/.local/bin/
```

### Python (reference)

```bash
uv sync
```

## Usage

### `unfluff reduce` — Syntax-guided reduction (default)

```bash
# Reduce using a pytest interestingness test (recommended)
unfluff reduce --test test_interesting.py::test_still_fails input.py

# Reduce using a shell command
unfluff reduce --test-cmd "grep -q 'error'" input.py

# Auto-reduce to smallest valid program (no test needed)
unfluff reduce --auto input.py

# Limit reduction time
unfluff reduce --test test_interesting.py --max-time 30m --max-tests 1000 input.py

# Use Python implementation (legacy)
unfluff --legacy reduce --test test_interesting.py::test_still_fails input.py
```

### `unfluff check` — Static analysis and fixes

```bash
# Check files for reducible patterns
unfluff check src/**/*.py

# Apply safe fixes automatically
unfluff check --fix src/**/*.py

# Apply all fixes (including unsafe ones like dead code removal)
unfluff check --unsafe-fixes src/**/*.py

# Output as JSON
unfluff check --output-format json src/**/*.py

# Filter by rule
unfluff check --select RED200,RED201 src/**/*.py
```

### `unfluff shrink` — Shrinkray-compatible interface

```bash
unfluff shrink "./check.sh" input.py
```

### Check Rules

| Code   | Description                        | Safe?  |
| ------ | ---------------------------------- | ------ |
| RED100 | Dead function (no callers)         | unsafe |
| RED101 | Dead class (no instantiations)     | unsafe |
| RED102 | Unused variable assignment         | unsafe |
| RED200 | Constant expression simplification | safe   |
| RED201 | Redundant parentheses              | safe   |
| RED202 | Unnecessary semicolon              | safe   |
| RED203 | Trailing whitespace                | safe   |
| RED204 | Redundant newline                  | safe   |

## Example: Reducing a Bug Trigger

Given a Python file that triggers a bug when `fibonacci` is called with
`print()`:

**Before** (`input.py`):

```python
import sys

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def unused_helper(x):
    return x * 2

def also_unused():
    result = unused_helper(5)
    return result

class MyClass:
    def __init__(self):
        self.value = 42

    def method(self):
        return self.value

if __name__ == "__main__":
    for i in range(10):
        print(fibonacci(i))
```

Write a pytest interestingness test (`test_interesting.py`):

```python
import sys

def test_still_fails():
    """Exit 0 = candidate is still interesting (bug still present)."""
    candidate = sys.argv[1]
    content = open(candidate).read()
    assert "def fibonacci" in content and "print(" in content
```

Run the reducer:

```bash
unfluff reduce --test test_interesting.py::test_still_fails input.py
```

**After** (`input.py`):

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print(fibonacci(10))
```

**Diff:**

```diff
-import sys
-
 def fibonacci(n):
     if n <= 1:
         return n
     return fibonacci(n - 1) + fibonacci(n - 2)

-def unused_helper(x):
-    return x * 2
-
-def also_unused():
-    result = unused_helper(5)
-    return result
-
-class MyClass:
-    def __init__(self):
-        self.value = 42
-
-    def method(self):
-        return self.value
-
-if __name__ == "__main__":
-    for i in range(10):
-        print(fibonacci(i))
+print(fibonacci(10))
```

The reducer removed the unused `import sys`, the `unused_helper` and
`also_unused` functions, the `MyClass` class, and simplified the `if __name__`
block — while preserving the core `fibonacci` function and the `print()` call
that triggers the bug.

## Example: Checking and Fixing Code

**Input** (`demo.py`):

```python
import os

def greet(name):
    print(f"Hello, {name}")

def unused_helper(x):
    return x * 2

count = 0;;

class EmptyClass:
    pass

message = "hello"   

greet("world")
```

Run the checker:

```bash
unfluff check demo.py
```

**Output:**

```
demo.py:14:17: RED203 Trailing whitespace
    14 | message = "hello"   
      ^^^^^^^^^^^^^^^^^ RED203

demo.py:9:10: RED202 Unnecessary semicolon
    9 | count = 0;;
     ^^^^^^^^^^^ RED202

demo.py:14:1: RED102 Unused variable assignment
    14 | message = "hello"   
      ^^^^^^^^^^^^^^^^^ RED102

demo.py:9:1: RED102 Unused variable assignment
    9 | count = 0;;
     ^^^^^^^^^^^ RED102

demo.py:6:1: RED100 Dead function (no callers)
    6 | def unused_helper(x):
     ^^^^^^^^^^^^^^^^^^^^^ RED100

demo.py:11:1: RED101 Dead class (no instantiations)
    11 | class EmptyClass:
      ^^^^^^^^^^^^^^^^^ RED101

Found 6 issues (2 safe, 4 unsafe).
```

Apply safe fixes:

```bash
unfluff check --fix demo.py
```

**After** (`demo.py`):

```python
import os

def greet(name):
    print(f"Hello, {name}")

def unused_helper(x):
    return x * 2

count = 0;

class EmptyClass:
    pass

message = "hello"

greet("world")
```

The `--fix` flag applies only safe fixes (RED200–RED204). Use `--unsafe-fixes`
to also remove dead functions, dead classes, and unused assignments.

## Development

### Rust (primary)

```bash
cargo build --release      # build
cargo test                 # test
cargo clippy               # lint
cargo fmt                  # format
```

### Python (reference)

```bash
uv run ruff check src/theseus_ship/     # lint
uv run ruff format src/theseus_ship/    # format
uv run ty check src/theseus_ship/       # type check
uv run pytest tests/                    # test
```

## License

MIT
