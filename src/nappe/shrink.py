from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from nappe.cache import Cache
from nappe.grammar import Grammar, detect_language, load_grammar
from nappe.parser import parse_source
from nappe.transforms import apply_transform, generate_candidates


@dataclass
class ShrinkResult:
    source: bytes
    tests_run: int
    elapsed_seconds: float
    output_path: str | None


class ShrinkReducer:
    """Shrinkray-compatible reducer using tree-sitter.

    Mirrors shrinkray's interface: test receives candidate on stdin AND as
    a file argument. Uses Perses algorithm internally.
    """

    def __init__(
        self,
        grammar: Grammar,
        test_command: str,
        timeout: float = 60.0,
        max_time: float | None = None,
        max_tests: int | None = None,
        parallelism: int = 1,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        self._grammar = grammar
        self._test_command = test_command
        self._cmd_parts = shlex.split(test_command)
        self._timeout = timeout
        self._max_time = max_time
        self._max_tests = max_tests
        self._parallelism = parallelism
        self._verbose = verbose
        self._quiet = quiet
        self._cache = Cache()
        self._tests_run = 0

    def reduce(
        self,
        source: bytes,
        filename: str | None = None,
    ) -> ShrinkResult:
        start_time = time.monotonic()
        current_source = source
        self._tests_run = 0

        while not self._should_stop(self._tests_run, start_time):
            result = parse_source(current_source, self._grammar)
            candidates = generate_candidates(result, self._grammar)

            if not candidates:
                break

            base_error_count = result.error_node_count
            accepted = False
            for candidate in candidates:
                if self._should_stop(self._tests_run, start_time):
                    break

                new = apply_transform(
                    current_source,
                    candidate,
                    self._grammar,
                    root_node=result.root_node,
                    base_error_count=base_error_count,
                )
                if new is None:
                    continue

                new_source, _ = new
                if self._is_interesting(new_source, filename):
                    self._log(
                        f"accepted {candidate.kind.value} at "
                        f"bytes {candidate.target.byte_start}-{candidate.target.byte_end}"
                    )
                    current_source = new_source
                    accepted = True
                    break
                else:
                    self._log(
                        f"rejected {candidate.kind.value} at "
                        f"bytes {candidate.target.byte_start}-{candidate.target.byte_end}"
                    )

            if not accepted:
                break

        elapsed = time.monotonic() - start_time
        return ShrinkResult(
            source=current_source,
            tests_run=self._tests_run,
            elapsed_seconds=elapsed,
            output_path=filename,
        )

    def _is_interesting(self, source: bytes, filename: str | None) -> bool:
        cached = self._cache.get(source)
        if cached is not None:
            return cached

        self._tests_run += 1

        try:
            fd, temp_path = tempfile.mkstemp(suffix=".py")
            try:
                os.write(fd, source)
                os.close(fd)

                proc = subprocess.run(
                    self._cmd_parts + [temp_path],
                    input=source,
                    capture_output=True,
                    timeout=self._timeout,
                )
                is_interesting = proc.returncode == 0
            except subprocess.TimeoutExpired:
                is_interesting = False
            except Exception:
                is_interesting = False
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        except Exception:
            is_interesting = False

        self._cache.set(source, is_interesting)
        return is_interesting

    def _should_stop(self, tests_run: int, start_time: float) -> bool:
        if self._max_tests is not None and tests_run >= self._max_tests:
            return True
        if self._max_time is not None:
            elapsed = time.monotonic() - start_time
            if elapsed >= self._max_time:
                return True
        return False

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg, flush=True)


def run_shrink(
    test_command: str,
    filename: str,
    timeout: float = 60.0,
    max_time: float | None = None,
    max_tests: int | None = None,
    parallelism: int = 1,
    backup: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> int:
    """Run shrinkray-compatible reduction. Returns exit code."""
    input_path = (
        os.path.join(os.getcwd(), filename) if not os.path.isabs(filename) else filename
    )

    if not os.path.exists(input_path):
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        with open(input_path, "rb") as f:
            source = f.read()
    except OSError as e:
        print(f"Error reading {input_path}: {e}", file=sys.stderr)
        return 1

    lang = detect_language(input_path)
    grammar = load_grammar(lang)

    if backup:
        backup_path = input_path + os.extsep + backup
    else:
        backup_path = input_path + os.extsep + "bak"

    try:
        with open(backup_path, "wb") as f:
            f.write(source)
    except OSError as e:
        print(f"Warning: could not create backup: {e}", file=sys.stderr)

    reducer = ShrinkReducer(
        grammar=grammar,
        test_command=test_command,
        timeout=timeout,
        max_time=max_time,
        max_tests=max_tests,
        parallelism=parallelism,
        verbose=verbose,
        quiet=quiet,
    )

    original_size = len(source)
    result = reducer.reduce(source, filename=input_path)

    try:
        with open(input_path, "wb") as f:
            f.write(result.source)
    except OSError as e:
        print(f"Error writing {input_path}: {e}", file=sys.stderr)
        return 1

    if not quiet:
        reduced_size = len(result.source)
        pct = (1 - reduced_size / original_size) * 100 if original_size > 0 else 0
        elapsed = result.elapsed_seconds
        if elapsed < 60:
            time_str = f"{elapsed:.1f}s"
        else:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            time_str = f"{mins}m {secs}s"
        print(
            f"Reduced {original_size} -> {reduced_size} bytes "
            f"({pct:.0f}% reduction) in {time_str} "
            f"({result.tests_run} tests)",
            file=sys.stderr,
        )

    return 0
