from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from theseus_ship.grammar import Grammar
from theseus_ship.parser import parse_source
from theseus_ship.transforms import apply_transform, generate_candidates


@dataclass
class ReduceResult:
    source: bytes
    tests_run: int
    elapsed_seconds: float


class _Cache:
    def __init__(self) -> None:
        self._results: dict[str, bool] = {}

    def get(self, source: bytes) -> bool | None:
        key = hashlib.sha256(source).hexdigest()
        return self._results.get(key)

    def set(self, source: bytes, result: bool) -> None:
        key = hashlib.sha256(source).hexdigest()
        self._results[key] = result


class Reducer:
    def __init__(
        self,
        grammar: Grammar,
        test_spec: str | None = None,
        test_command: str | None = None,
        max_time: float | None = None,
        max_tests: int | None = None,
        jobs: int = 1,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        if test_spec is None and test_command is None:
            msg = "Either test_spec or test_command must be provided"
            raise ValueError(msg)
        self._grammar = grammar
        self._test_spec = test_spec
        self._test_command = test_command
        self._max_time = max_time
        self._max_tests = max_tests
        self._jobs = jobs
        self._verbose = verbose
        self._quiet = quiet
        self._cache = _Cache()
        self._tests_run = 0

    def reduce(self, source: bytes) -> ReduceResult:
        start_time = time.monotonic()
        current_source = source
        self._tests_run = 0

        while not self._should_stop(self._tests_run, start_time):
            result = parse_source(current_source, self._grammar)
            candidates = generate_candidates(result, self._grammar)

            if not candidates:
                break

            accepted = False
            for candidate in candidates:
                if self._should_stop(self._tests_run, start_time):
                    break

                new = apply_transform(
                    current_source, candidate, self._grammar, root_node=result.root_node
                )
                if new is None:
                    continue

                new_source, _ = new
                if self._is_interesting(new_source):
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

        if self._test_spec is not None:
            is_interesting = self._is_interesting_pytest(source)
        else:
            is_interesting = self._is_interesting_command(source)

        self._cache.set(source, is_interesting)
        return is_interesting

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
        assert self._test_command is not None
        try:
            cmd_parts = shlex.split(self._test_command)
            result = subprocess.run(
                cmd_parts,
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

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg, flush=True)
