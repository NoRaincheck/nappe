import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from nappe.cache import Cache
from nappe.shrink import ShrinkReducer, run_shrink


class TestShrinkCache:
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


class TestShrinkReducer:
    def test_is_interesting_success(self) -> None:
        from nappe.grammar import load_grammar

        grammar = load_grammar("python")
        reducer = ShrinkReducer(grammar, test_command="true")
        assert reducer._is_interesting(b"anything", None) is True

    def test_is_interesting_failure(self) -> None:
        from nappe.grammar import load_grammar

        grammar = load_grammar("python")
        reducer = ShrinkReducer(grammar, test_command="false")
        assert reducer._is_interesting(b"anything", None) is False

    def test_is_interesting_receives_stdin(self) -> None:
        from nappe.grammar import load_grammar

        grammar = load_grammar("python")
        reducer = ShrinkReducer(grammar, test_command="cat")
        assert reducer._is_interesting(b"test content", None) is True

    def test_is_interesting_passes_file_arg(self) -> None:
        from nappe.grammar import load_grammar

        grammar = load_grammar("python")
        reducer = ShrinkReducer(
            grammar, test_command="test -f"
        )
        assert reducer._is_interesting(b"anything", None) is True


@pytest.mark.slow
class TestRunShrink:
    def test_file_not_found(self) -> None:
        assert run_shrink("true", "nonexistent.py") == 1

    def test_basic_reduction(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, dir="/tmp"
        ) as f:
            f.write("def foo(): pass\ndef bar(): return 42\n")
            input_path = f.name

        try:
            ret = run_shrink("true", input_path, quiet=True)
            assert ret == 0
            content = Path(input_path).read_bytes()
            assert len(content) <= 40
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(input_path + ".bak").unlink(missing_ok=True)

    def test_creates_backup(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, dir="/tmp"
        ) as f:
            f.write("x = 1\n")
            input_path = f.name

        try:
            run_shrink("false", input_path, quiet=True)
            assert Path(input_path + ".bak").exists()
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(input_path + ".bak").unlink(missing_ok=True)

    def test_custom_backup(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, dir="/tmp"
        ) as f:
            f.write("x = 1\n")
            input_path = f.name

        try:
            run_shrink("false", input_path, backup="orig", quiet=True)
            assert Path(input_path + ".orig").exists()
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(input_path + ".orig").unlink(missing_ok=True)


@pytest.mark.slow
class TestCLIShrinkSubcommand:
    def test_shrink_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "nappe", "shrink", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "shrink" in result.stdout.lower()

    def test_shrink_missing_args(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "nappe", "shrink"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
