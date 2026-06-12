# Benchmarks

Comparison of the Python and Rust implementations of unfluff.

## Auto-reduce mode (`--auto`)

| Input Size           | Python | Rust   | Speedup  |
| -------------------- | ------ | ------ | -------- |
| 60 B (`simple.py`)   | 0.093s | 0.007s | **13x**  |
| 297 B (`complex.py`) | 0.086s | 0.007s | **12x**  |
| 6 KB (generated)     | 2.80s  | 0.93s  | **3.0x** |
| 25 KB (generated)    | 38.5s  | 12.8s  | **3.0x** |

Both implementations produce identical reduction results (same output size and
test count).

## Notes

- Consistent ~3x speedup on files where the interestingness test itself is fast
  (auto mode uses internal parsing)
- ~12-13x speedup on tiny files (startup overhead dominated by Python VM init)
- The gap widens with file size since parsing/CST-walk is the bottleneck
- Python times out (>2min) on 115KB files; Rust handles those in ~1-2 minutes
