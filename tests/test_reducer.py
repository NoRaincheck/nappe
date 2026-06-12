from pathlib import Path
from unittest.mock import patch

from theseus_ship.grammar import load_grammar
from theseus_ship.reducer import ReduceResult, Reducer, _Cache


FIXTURES = Path(__file__).parent / "fixtures"


class TestCache:
    def test_hit_miss(self) -> None:
        cache = _Cache()
        assert cache.get(b"hello") is None
        cache.set(b"hello", True)
        assert cache.get(b"hello") is True

    def test_deterministic(self) -> None:
        cache = _Cache()
        cache.set(b"test data", False)
        assert cache.get(b"test data") is False
        assert cache.get(b"different") is None


class TestIsInteresting:
    def test_success(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, "true")
        assert reducer._is_interesting(b"anything") is True

    def test_failure(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, "false")
        assert reducer._is_interesting(b"anything") is False

    def test_timeout(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, "sleep 100")

        import subprocess

        original_run = subprocess.run

        def mock_run(*args, **kwargs):
            kwargs["timeout"] = 0.01
            return original_run(*args, **kwargs)

        with patch("theseus_ship.reducer.subprocess.run", side_effect=mock_run):
            assert reducer._is_interesting(b"anything") is False


class TestShouldStop:
    def test_max_tests(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, "true", max_tests=5)
        import time

        start = time.monotonic()
        assert reducer._should_stop(4, start) is False
        assert reducer._should_stop(5, start) is True

    def test_max_time(self) -> None:
        grammar = load_grammar("python")
        reducer = Reducer(grammar, "true", max_time=0.001)
        import time

        start = time.monotonic()
        time.sleep(0.01)
        assert reducer._should_stop(0, start) is True


class TestReduce:
    def test_uninteresting_input(self) -> None:
        grammar = load_grammar("python")
        source = b"pass\n"
        reducer = Reducer(grammar, "false")
        result = reducer.reduce(source)
        assert result.source == source
        assert result.tests_run == 0

    def test_reduce_small_input(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        reducer = Reducer(grammar, "true", max_tests=1, verbose=False, quiet=True)
        result = reducer.reduce(source)
        assert result.tests_run >= 1
        assert len(result.source) <= len(source)

    def test_max_tests_limit(self) -> None:
        grammar = load_grammar("python")
        source = b"def foo(): pass\nx = 1\n"
        reducer = Reducer(grammar, "true", max_tests=2, quiet=True)
        result = reducer.reduce(source)
        assert result.tests_run <= 2

    def test_result_type(self) -> None:
        grammar = load_grammar("python")
        source = b"pass\n"
        reducer = Reducer(grammar, "false")
        result = reducer.reduce(source)
        assert isinstance(result, ReduceResult)
        assert isinstance(result.source, bytes)
        assert isinstance(result.tests_run, int)
        assert isinstance(result.elapsed_seconds, float)
