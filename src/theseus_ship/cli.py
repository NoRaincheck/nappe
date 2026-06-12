from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from theseus_ship.grammar import detect_language, load_grammar
from theseus_ship.reducer import Reducer


def parse_duration(s: str) -> float:
    m = re.fullmatch(r"(\d+)(s|m|h)", s)
    if m is None:
        msg = f"Invalid duration: {s!r} (use e.g. 30s, 5m, 1h)"
        raise argparse.ArgumentTypeError(msg)
    value, unit = int(m.group(1)), m.group(2)
    return value * {"s": 1, "m": 60, "h": 3600}[unit]


def _format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lang", help="Override language detection")
    parser.add_argument(
        "-o", "--output", help="Output file path (default: overwrite input)"
    )
    parser.add_argument(
        "--max-time", type=parse_duration, help="Maximum reduction time (e.g. 30m, 1h)"
    )
    parser.add_argument("--max-tests", type=int, help="Maximum test invocations")
    parser.add_argument(
        "-j", "--jobs", type=int, default=1, help="Parallel test workers"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="theseus-ship",
        description="Syntax-guided program reduction (Perses algorithm)",
    )

    test_group = parser.add_mutually_exclusive_group(required=False)
    test_group.add_argument(
        "--test",
        help="Pytest test specification (e.g. test_file.py::test_name)",
    )
    test_group.add_argument(
        "--test-cmd",
        help="Shell command (exit 0 = interesting, receives source on stdin)",
    )
    test_group.add_argument(
        "--auto",
        action="store_true",
        help="Reduce to smallest syntactically valid program (no test needed)",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Reject any parse errors, including pre-existing ones",
    )

    parser.add_argument("input", nargs="?", help="Source file to reduce")
    _add_common_args(parser)

    return parser


def _build_shrink_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="theseus-ship shrink",
        description="Shrinkray-compatible reduction (test <file>)",
    )
    parser.add_argument("test", help="Interestingness test command")
    parser.add_argument("file", help="Source file to reduce")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-test timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--backup",
        default="",
        help="Backup file suffix (default: .bak)",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=1,
        help="Number of parallel test workers",
    )
    _add_common_args(parser)

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "shrink":
        parser = _build_shrink_parser()
        args = parser.parse_args(argv[1:])
        args.command = "shrink"
        return args

    parser = _build_parser()
    args = parser.parse_args(argv)
    args.command = None
    return args


def main() -> None:
    args = parse_args()
    if args.command == "shrink":
        sys.exit(_run_shrink(args))
    else:
        sys.exit(_run(args))


def _run_shrink(args: argparse.Namespace) -> int:
    from theseus_ship.shrink import run_shrink

    return run_shrink(
        test_command=args.test,
        filename=args.file,
        timeout=args.timeout,
        max_time=args.max_time,
        max_tests=args.max_tests,
        parallelism=args.parallelism,
        backup=args.backup,
        verbose=args.verbose,
        quiet=args.quiet,
    )


def _run(args: argparse.Namespace) -> int:
    if not args.input:
        print(
            "Error: input file required (or use: theseus-ship shrink <test> <file>)",
            file=sys.stderr,
        )
        return 1

    if not args.test and not args.test_cmd and not args.auto:
        print("Error: --test, --test-cmd, or --auto required", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        source = input_path.read_bytes()
    except OSError as e:
        print(f"Error reading {input_path}: {e}", file=sys.stderr)
        return 1

    lang = args.lang or detect_language(str(input_path))
    grammar = load_grammar(lang)

    output_path = Path(args.output) if args.output else input_path

    reducer = Reducer(
        grammar=grammar,
        test_spec=args.test,
        test_command=args.test_cmd,
        auto=args.auto,
        max_time=args.max_time,
        max_tests=args.max_tests,
        jobs=args.jobs,
        verbose=args.verbose,
        quiet=args.quiet,
        strict=args.strict,
    )

    original_size = len(source)
    result = reducer.reduce(source)
    reduced_size = len(result.source)

    try:
        output_path.write_bytes(result.source)
    except OSError as e:
        print(f"Error writing {output_path}: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        pct = (1 - reduced_size / original_size) * 100 if original_size > 0 else 0
        print(
            f"Reduced {original_size} -> {reduced_size} bytes "
            f"({pct:.0f}% reduction) in {_format_time(result.elapsed_seconds)} "
            f"({result.tests_run} tests)",
            file=sys.stderr,
        )

    return 0
