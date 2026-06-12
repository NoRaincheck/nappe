from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nappe.grammar import load_grammar
from nappe.cache import Cache
from nappe.reducer import ReduceResult, Reducer


FIXTURES = Path(__file__).parent / "fixtures"


class TestCache:
    def test_hit_miss(self) -> None:
        cache = Cache()
        assert cache.get(b"hello") is None
        cache.set(b"hello", True)
        assert cache.get(b"hello") is True

    def test_deterministic(self) -> None:
        cache = Cache()
        cache.set(b"test data", False)
        assert cache.get(b"test data") is False
        assert cache.get(b"different") is None


@pytest.mark.slow
class TestIsInterestingCommand:
    def test_success(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="true")
        assert reducer._is_interesting(b"anything") is True

    def test_failure(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="false")
        assert reducer._is_interesting(b"anything") is False

    def test_timeout(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="sleep 100")

        import subprocess

        original_run = subprocess.run

        def mock_run(*args, **kwargs):
            kwargs["timeout"] = 0.01
            return original_run(*args, **kwargs)

        with patch("nappe.reducer.subprocess.run", side_effect=mock_run):
            assert reducer._is_interesting(b"anything") is False


@pytest.mark.slow
class TestIsInterestingPytest:
    def test_passing_test(self) -> None:
        grammar = load_grammar("python")
        test_spec = str(FIXTURES / "interesting_test.py::test_still_fails")
        reducer = Reducer(grammar, test_spec=test_spec)
        source = b"def fibonacci(n): pass\n"
        assert reducer._is_interesting(source) is True

    def test_failing_test(self) -> None:
        grammar = load_grammar("python")
        test_spec = str(FIXTURES / "interesting_test.py::test_still_fails")
        reducer = Reducer(grammar, test_spec=test_spec)
        source = b"def other(): pass\n"
        assert reducer._is_interesting(source) is False


class TestShouldStop:
    def test_max_tests(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="true", max_tests=5)
        import time

        start = time.monotonic()
        assert reducer._should_stop(4, start) is False
        assert reducer._should_stop(5, start) is True

    def test_max_time(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="true", max_time=0.001)
        import time

        start = time.monotonic()
        time.sleep(0.01)
        assert reducer._should_stop(0, start) is True


@pytest.mark.slow
class TestReduce:
    def test_uninteresting_input(self) -> None:
        grammar = load_grammar("python")
        source = b"pass\n"
        reducer = Reducer(grammar, test_command="false")
        result = reducer.reduce(source)
        assert result.source == source
        assert result.tests_run == 0

    def test_reduce_small_input(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        reducer = Reducer(
            grammar, test_command="true", max_tests=1, verbose=False, quiet=True
        )
        result = reducer.reduce(source)
        assert result.tests_run >= 1
        assert len(result.source) <= len(source)

    def test_max_tests_limit(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        reducer = Reducer(grammar, test_command="true", max_tests=2, quiet=True)
        result = reducer.reduce(source)
        assert result.tests_run <= 2

    def test_result_type(self) -> None:
        grammar = load_grammar("python")
        source = b"pass\n"
        reducer = Reducer(grammar, test_command="false")
        result = reducer.reduce(source)
        assert isinstance(result, ReduceResult)
        assert isinstance(result.source, bytes)
        assert isinstance(result.tests_run, int)
        assert isinstance(result.elapsed_seconds, float)

    def test_requires_test_spec_or_command(self) -> None:
        grammar = load_grammar("python")
        try:
            Reducer(grammar)
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestProgressReporting:
    def test_progress_printed_when_not_quiet(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\ndef bar(): pass\n"
        reducer = Reducer(grammar, auto=True, quiet=False)
        with patch("nappe.reducer.print") as mock_print:
            reducer.reduce(source)
            assert mock_print.call_count > 0

    def test_progress_suppressed_when_quiet(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\ndef bar(): pass\n"
        reducer = Reducer(grammar, auto=True, quiet=True)
        with patch("nappe.reducer.print") as mock_print:
            reducer.reduce(source)
            mock_print.assert_not_called()


class TestAutoMode:
    def test_no_test_required(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, auto=True)
        assert reducer._auto is True

    def test_auto_reduces_valid_program(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\ndef bar(): pass\n"
        reducer = Reducer(grammar, auto=True, quiet=True)
        result = reducer.reduce(source)
        assert len(result.source) <= len(source)
        from nappe.parser import parse_source

        final = parse_source(result.source, grammar)
        assert final.error_node_count == 0

    def test_auto_preserves_syntax(self) -> None:
        grammar = load_grammar("python")
        source = b"def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)\n\ndef unused():\n    x = 1\n    return x\n"
        reducer = Reducer(grammar, auto=True, quiet=True)
        result = reducer.reduce(source)
        from nappe.parser import parse_source

        final = parse_source(result.source, grammar)
        assert final.error_node_count == 0

    def test_auto_noop_on_invalid_start(self) -> None:
        grammar = load_grammar("python")
        source = b"def (invalid:\n"
        reducer = Reducer(grammar, auto=True, quiet=True)
        result = reducer.reduce(source)
        assert result.source == source
        assert result.tests_run > 0


class TestStrictMode:
    def test_strict_rejects_transforms_with_errors(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\ndef bar(): pass\n"
        reducer = Reducer(
            grammar, test_command="true", strict=True, quiet=True
        )
        result = reducer.reduce(source)
        from nappe.parser import parse_source

        final = parse_source(result.source, grammar)
        assert final.error_node_count == 0

    def test_non_strict_allows_maintaining_error_count(self) -> None:
        grammar = load_grammar("python")
        source = b"def (broken:\n"
        reducer = Reducer(
            grammar, test_command="true", strict=False, quiet=True
        )
        result = reducer.reduce(source)
        from nappe.parser import parse_source

        final = parse_source(result.source, grammar)
        assert final.error_node_count > 0

    def test_strict_stores_flag(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="true", strict=True)
        assert reducer._strict is True

    def test_non_strict_default(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, test_command="true")
        assert reducer._strict is False


class TestParallel:
    def test_parallel_same_as_sequential(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\ndef bar(): pass\n"

        reducer_seq = Reducer(grammar, auto=True, jobs=1, quiet=True)
        result_seq = reducer_seq.reduce(source)

        reducer_par = Reducer(grammar, auto=True, jobs=2, quiet=True)
        result_par = reducer_par.reduce(source)

        assert result_par.source == result_seq.source

    def test_jobs_passed_to_pool(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, auto=True, jobs=4, quiet=True)
        sources = [b"pass\n", b"x = 1\n"]
        with patch(
            "nappe.reducer.concurrent.futures.ProcessPoolExecutor"
        ) as mock_pool:
            mock_instance = Mock()
            mock_pool.return_value.__enter__ = Mock(return_value=mock_instance)
            mock_pool.return_value.__exit__ = Mock(return_value=False)
            mock_instance.map.return_value = [True, True]
            results = reducer._test_batch(sources)
            mock_pool.assert_called_with(max_workers=4)
            assert results == [True, True]

    def test_sequential_when_jobs_1(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, auto=True, jobs=1, quiet=True)
        sources = [b"pass\n", b"x = 1\n"]
        results = reducer._test_batch(sources)
        assert len(results) == 2
        assert all(isinstance(r, bool) for r in results)
