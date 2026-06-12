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
# Reduce using a pytest interestingness test (recommended)
uv run theseus-ship --test test_interesting.py::test_still_fails input.py

# Reduce using a shell command (backward compatible)
uv run theseus-ship --test-cmd "grep -q 'error'" input.py

# Shrinkray-compatible interface (test <file>)
uv run theseus-ship shrink "./check.sh" input.py

# Limit reduction time
uv run theseus-ship --test test_interesting.py --max-time 30m --max-tests 1000 input.py
```

## Example

Given a Python file that triggers a bug when `fibonacci` is called with `print()`:

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
import os

def test_still_fails():
    """Exit 0 = candidate is still interesting (bug still present)."""
    candidate = os.environ["THESEUS_CANDIDATE"]
    content = open(candidate).read()
    assert "def fibonacci" in content and "print(" in content
```

Run the reducer:
```bash
uv run theseus-ship --test test_interesting.py::test_still_fails input.py
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

The reducer removed the unused `import sys`, the `unused_helper` and `also_unused` functions, the `MyClass` class, and simplified the `if __name__` block — while preserving the core `fibonacci` function and the `print()` call that triggers the bug.

## Development

```bash
uv run ruff check src/     # lint
uv run ruff format src/    # format
uv run ty check src/       # type check
```

## License

MIT
