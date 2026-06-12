from __future__ import annotations

import concurrent.futures
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from nappe.cache import Cache
from nappe.escapes import try_escape_transforms
from nappe.grammar import Grammar, load_grammar
from nappe.parser import parse_source
from nappe.token_reduce import token_reduce
from nappe.transforms import apply_transform, generate_candidates
from nappe.tree import ParseResult


@dataclass
class ReduceResult:
    source: bytes
    tests_run: int
    elapsed_seconds: float


def _run_interesting_test(
    source: bytes,
    auto: bool,
    test_spec: str | None,
    test_command: str | None,
    lang_name: str,
) -> bool:
    if auto:
        grammar = load_grammar(lang_name)
        result = parse_source(source, grammar)
        return result.error_node_count == 0

    if test_spec is not None:
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".py", delete=False
            ) as f:
                f.write(source)
                temp_path = f.name
            try:
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        temp_path,
                        test_spec,
                        "-x",
                        "--tb=no",
                        "-q",
                    ],
                    capture_output=True,
                    timeout=60,
                )
                return proc.returncode == 0
            except subprocess.TimeoutExpired, Exception:
                return False
            finally:
                os.unlink(temp_path)
        except Exception:
            return False

    assert test_command is not None
    cmd_parts = shlex.split(test_command)
    try:
        proc = subprocess.run(
            cmd_parts,
            input=source,
            capture_output=True,
            timeout=60,
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired, Exception:
        return False


class Reducer:
    def __init__(
        self,
        grammar: Grammar,
        test_spec: str | None = None,
        test_command: str | None = None,
        auto: bool = False,
        max_time: float | None = None,
        max_tests: int | None = None,
        jobs: int = 1,
        verbose: bool = False,
        quiet: bool = False,
        strict: bool = False,
    ) -> None:
        if not auto and test_spec is None and test_command is None:
            msg = "Either test_spec, test_command, or auto=True must be provided"
            raise ValueError(msg)
        self._grammar = grammar
        self._test_spec = test_spec
        self._test_command = test_command
        self._auto = auto
        self._max_time = max_time
        self._max_tests = max_tests
        self._jobs = jobs
        self._verbose = verbose
        self._quiet = quiet
        self._strict = strict
        self._cache = Cache()
        self._tests_run = 0
        self._cmd_parts = shlex.split(test_command) if test_command else None

    def _test_batch(self, sources: list[bytes]) -> list[bool]:
        if self._jobs <= 1:
            return [self._is_interesting(s) for s in sources]

        results: list[bool | None] = [None] * len(sources)
        uncached: list[tuple[int, bytes]] = []
        for i, source in enumerate(sources):
            cached = self._cache.get(source)
            if cached is not None:
                results[i] = cached
            else:
                uncached.append((i, source))

        if uncached:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self._jobs
            ) as executor:
                test_results = list(
                    executor.map(
                        _run_interesting_test,
                        [s for _, s in uncached],
                        [self._auto] * len(uncached),
                        [self._test_spec] * len(uncached),
                        [self._test_command] * len(uncached),
                        [self._grammar.name] * len(uncached),
                    )
                )

            for (idx, source), is_interesting in zip(uncached, test_results):
                self._tests_run += 1
                self._cache.set(source, is_interesting)
                results[idx] = is_interesting

        return [r if r is not None else False for r in results]

    def reduce(self, source: bytes) -> ReduceResult:
        start_time = time.monotonic()
        current_source = source
        current_result: ParseResult | None = None
        self._tests_run = 0
        prev_size: int | None = None

        for escape_round in range(2):
            while not self._should_stop(self._tests_run, start_time):
                if (
                    current_result is None
                    or current_result.source_bytes != current_source
                ):
                    current_result = parse_source(current_source, self._grammar)
                candidates = generate_candidates(current_result, self._grammar)

                if not candidates:
                    break

                base_error_count = current_result.error_node_count
                accepted = False

                for batch_start in range(0, len(candidates), self._jobs):
                    if self._should_stop(self._tests_run, start_time):
                        break

                    batch = []
                    for candidate in candidates[batch_start : batch_start + self._jobs]:
                        if self._should_stop(self._tests_run, start_time):
                            break

                        new = apply_transform(
                            current_source,
                            candidate,
                            self._grammar,
                            root_node=current_result.root_node,
                            base_error_count=base_error_count,
                            old_result=current_result,
                            strict=self._strict,
                            is_interesting=self._is_interesting,
                        )
                        if new is None:
                            continue
                        batch.append((candidate, new[0], new[1]))

                    if not batch:
                        continue

                    sources = [s for _, s, _ in batch]
                    test_results = self._test_batch(sources)

                    for (candidate, new_source, new_result), is_interesting in zip(
                        batch, test_results
                    ):
                        if is_interesting:
                            self._log(
                                f"accepted {candidate.kind.value} at "
                                f"bytes {candidate.target.byte_start}-{candidate.target.byte_end}"
                            )
                            elapsed = time.monotonic() - start_time
                            self._print_progress(
                                len(new_source), prev_size, self._tests_run, elapsed
                            )
                            prev_size = len(current_source)
                            current_source = new_source
                            current_result = new_result
                            accepted = True
                            break
                        else:
                            self._log(
                                f"rejected {candidate.kind.value} at "
                                f"bytes {candidate.target.byte_start}-{candidate.target.byte_end}"
                            )

                    if accepted:
                        break

                if not accepted:
                    break

            if escape_round == 0 and not self._should_stop(self._tests_run, start_time):
                escaped = try_escape_transforms(
                    current_source, self._grammar, self._is_interesting, max_attempts=50
                )
                if escaped != current_source:
                    prev_size = len(current_source)
                    current_source = escaped
                    current_result = None
                    elapsed = time.monotonic() - start_time
                    self._print_progress(
                        len(current_source), prev_size, self._tests_run, elapsed
                    )
                else:
                    break
            else:
                break

        if not self._should_stop(self._tests_run, start_time):
            token_result = token_reduce(
                current_source, self._grammar, self._is_interesting
            )
            if token_result != current_source:
                current_source = token_result

        elapsed = time.monotonic() - start_time
        final_size = len(current_source)
        self._print_summary(len(source), final_size, self._tests_run, elapsed)
        return ReduceResult(
            source=current_source,
            tests_run=self._tests_run,
            elapsed_seconds=elapsed,
        )

    def _is_interesting(self, source: bytes) -> bool:
        cached = self._cache.get(source)
        if cached is not None:
            return cached

        self._tests_run += 1

        if self._auto:
            is_interesting = self._is_interesting_auto(source)
        elif self._test_spec is not None:
            is_interesting = self._is_interesting_pytest(source)
        else:
            is_interesting = self._is_interesting_command(source)

        self._cache.set(source, is_interesting)
        return is_interesting

    def _is_interesting_auto(self, source: bytes) -> bool:
        result = parse_source(source, self._grammar)
        return result.error_node_count == 0

    def _is_interesting_pytest(self, source: bytes) -> bool:
        assert self._test_spec is not None
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    temp_path,
                    self._test_spec,
                    "-x",
                    "--tb=no",
                    "-q",
                ],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
        finally:
            os.unlink(temp_path)

    def _is_interesting_command(self, source: bytes) -> bool:
        assert self._cmd_parts is not None
        try:
            result = subprocess.run(
                self._cmd_parts,
                input=source,
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def _should_stop(self, tests_run: int, start_time: float) -> bool:
        if self._max_tests is not None and tests_run >= self._max_tests:
            return True
        if self._max_time is not None:
            elapsed = time.monotonic() - start_time
            if elapsed >= self._max_time:
                return True
        return False

    def _print_progress(
        self, size: int, prev_size: int | None, tests_run: int, elapsed: float
    ) -> None:
        if self._quiet:
            return
        if prev_size is not None:
            change = (size - prev_size) / prev_size * 100
            line = f"[{elapsed:.1f}s] {prev_size} → {size} bytes ({change:+.1f}%) | {tests_run} tests"
        else:
            line = f"[{elapsed:.1f}s] {size} bytes | {tests_run} tests"
        print(line, file=sys.stderr)

    def _print_summary(
        self, original: int, final: int, tests_run: int, elapsed: float
    ) -> None:
        if self._quiet:
            return
        if original > 0:
            pct = (1 - final / original) * 100
            line = f"Reduced: {original} → {final} bytes ({pct:.1f}% reduction) | {tests_run} tests | {elapsed:.1f}s"
        else:
            line = f"Reduced: {original} → {final} bytes | {tests_run} tests | {elapsed:.1f}s"
        print(line, file=sys.stderr)

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg, flush=True)
