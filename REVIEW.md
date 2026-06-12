# Program Reduction: A Survey and Assessment of theseus-ship

## Abstract

Program reduction — the automatic minimization of a failing test case to the
smallest input that preserves the failure — is a critical tool in software
debugging, compiler testing, and fuzzing. This paper surveys the landscape of
program reduction tools and techniques, situates **theseus-ship** (a pure Python
implementation of the Perses algorithm) within that landscape, evaluates its
novelty and gaps, and proposes concrete improvements for speed and alignment
with state-of-the-art goals.

---

## 1. The Problem

Given a program _P_ that exhibits a property _ψ_ (e.g., triggers a compiler
crash), program reduction seeks the smallest _P'_ such that _ψ(P')_ holds. The
ideal is global minimality; practical tools target weaker guarantees:

| Minimality Level   | Definition                                                                    |
| ------------------ | ----------------------------------------------------------------------------- |
| **1-minimal**      | No single element can be removed while preserving _ψ_                         |
| **1-tree-minimal** | No AST node can be further simplified (delete or unwrap) while preserving _ψ_ |
| **Global minimum** | No smaller program preserves _ψ_ (computationally intractable in general)     |

The difficulty is combinatorial: a 100-line file has 2^100 subsets. Tools must
exploit structure (syntax, grammar, program semantics) to navigate this space
efficiently.

---

## 2. Landscape of Existing Tools

### 2.1 Delta Debugging (ddmin)

**Zeller & Hildebrandt, 2002.** The foundational approach. Given a list of
elements (lines, tokens, characters), ddmin repeatedly halves partitions and
tests whether each half preserves the property. It guarantees 1-minimality but
operates on flat sequences, ignoring syntax.

- **Strengths:** Simple, general, language-independent.
- **Weaknesses:** Produces syntactically invalid intermediates (wasted test
  invocations on broken code), no structural awareness, O(n²) test invocations
  in the worst case.

### 2.2 Hierarchical Delta Debugging (HDD)

**Misherghi & Su, ICSE 2006.** Applies ddmin hierarchically: first at the line
level, then at the AST level, then at finer granularities. Exploits parse tree
structure to reduce the search space.

- **Strengths:** Structural awareness, better results than plain ddmin.
- **Weaknesses:** Still produces invalid intermediates at each level, requires a
  full parser, the hierarchy of levels is ad-hoc.

### 2.3 C-Reduce

**Regehr et al., 2012.** The de facto standard for C/C++ reduction. A Perl-based
tool that applies ~80 specialized transformation passes (via `clang_delta`,
`unifdef`, `clex`, and others) in a fixed order, interleaved with an
interestingness test.

- **Strengths:** Extremely effective for C/C++ (1.7k GitHub stars, widely used
  in compiler bug reporting), rich set of language-specific transformations,
  parallel execution.
- **Weaknesses:** Heavily C/C++-centric (though it works "pretty well" on other
  languages), complex Perl codebase, no formal guarantee of syntactic validity
  at every step, requires Clang as a dependency, 2,071 commits of accumulated
  complexity.

### 2.4 Shrinkray

**DRMacIver, 2023.** A modern Python-based multiformat reducer. Generic
algorithm with format-specific passes (C, Python, JSON, DIMACS CNF). Designed
for high parallelism and extensibility.

- **Strengths:** Multiformat, highly parallel, modern Python codebase, active
  development (590 commits), clean architecture.
- **Weaknesses:** Generic algorithm (not syntax-guided in the Perses sense),
  format-specific passes are basic, no formal syntactic validity guarantee.

### 2.5 Perses

**Sun et al., ICSE 2018.** A syntax-guided framework that exploits the formal
grammar of the language under reduction. Key innovations:

1. **Grammar normalization** to Perses Normal Form (PNF), introducing Kleene
   star/plus/optional quantifiers.
2. **Node-type-aware dispatch:** Kleene nodes use ddmin on children; regular
   nodes use BoundedBFS with the subsume relation to find replacement
   candidates.
3. **Reparse as the definitive validity gate:** every transform is validated by
   reparsing, ensuring _P_invalid = ∅_ in the search space.
4. **Priority queue** ordering nodes by token count (largest subtrees first).

**Evaluation:** Perses results are 2–45% the size of DD/HDD, using 23–47% of the
time. Compared to C-Reduce, Perses uses 38–60% of the reduction time.

### 2.6 bonsai

**nnunley, 2024.** A Rust reference implementation of Perses adapted for
tree-sitter grammars. Supports Python, JavaScript, and Rust. Uses tree-sitter's
supertype/subtype system and `locals.scm` queries for scope-aware transforms.

- **Strengths:** Rust performance, tree-sitter integration (incremental parsing,
  300+ language grammars available), scope-aware transforms (identifier
  unification, dead definition removal).
- **Weaknesses:** Early-stage (77 commits, 1 star), limited documentation,
  grammar support limited to 3 languages.

### 2.7 Vulcan

**Xu et al., OOPSLA 2023.** Addresses a fundamental limitation of Perses:
1-tree-minimality is not global minimality. Vulcan introduces transformations
that can escape local minima that Perses cannot, producing results 13–61%
smaller than Perses on some benchmarks.

- **Strengths:** Breaks the 1-minimality barrier, grammar-guided.
- **Weaknesses:** More complex, not yet widely adopted, no public implementation
  at scale.

### 2.8 T-Rec

**Xu et al., TOSEM 2025.** Operates at the lexical token level rather than the
AST level. Exploits the observation that many reductions are "horizontal"
(removing tokens within a node) rather than "vertical" (removing entire nodes).

- **Strengths:** Complements tree-level tools, can make reductions that Perses
  misses.
- **Weaknesses:** Requires both tokenization and AST information, no standalone
  implementation.

---

## 3. What is theseus-ship?

**theseus-ship** is a pure Python implementation of the Perses algorithm, based
on the Rust reference implementation bonsai. It is at version 0.1.0 and
implements:

| Component                             | Status                                                 |
| ------------------------------------- | ------------------------------------------------------ |
| Delete transform                      | Implemented, working                                   |
| Unwrap transform                      | Implemented (likely buggy — child byte offsets zeroed) |
| Unify identifiers                     | Stub only (Phase 5)                                    |
| Dead definition removal               | Stub only (Phase 5)                                    |
| Grammar normalization (PNF)           | Not implemented — uses raw tree-sitter grammars        |
| BoundedBFS / subsume relation         | Not implemented — simplified compatibility check       |
| Kleene-star ddmin dispatch            | Not implemented — all nodes treated as regular         |
| Priority queue (token-count ordering) | Implemented                                            |
| Reparse validity gate                 | Implemented                                            |
| Content-hash cache                    | Implemented                                            |
| Parallel execution                    | Parameter accepted, not implemented (jobs=1)           |
| Language support                      | Python only (extensible architecture)                  |
| Shrinkray compatibility               | Implemented                                            |

### 3.1 What is novel about theseus-ship?

**Short answer: the algorithm is not novel.** theseus-ship is a faithful
reimplementation of Perses. However, several design choices are distinctive:

1. **Pure Python with minimal dependencies.** Only `tree-sitter` and
   `tree-sitter-python` as runtime deps. This is the most accessible Perses
   implementation — no Rust toolchain, no Clang, no Perl. This lowers the
   barrier for adoption in Python-centric workflows.

2. **Pytest as a first-class interestingness test interface.**
   `--test test_file.py::test_name` is a natural fit for Python developers. No
   other Perses implementation offers this.

3. **Shrinkray-compatible interface.** The `shrink` subcommand bridges the
   Shrinkray ecosystem, allowing existing Shrinkray test scripts to run against
   a syntax-guided reducer.

4. **`--auto` mode.** Reduce to the smallest syntactically valid program without
   any external interestingness test. Useful for understanding what a parser
   considers valid.

5. **Error-tolerant reduction.** Handles inputs with pre-existing parse errors
   by tracking the initial error count and only rejecting transforms that
   _increase_ errors. This is a practical improvement over strict Perses, which
   assumes valid input.

---

## 4. Gaps and Missed Opportunities

### 4.1 Algorithmic Gaps (vs. Full Perses)

Theseus-ship implements a simplified version of Perses that misses several key
components:

| Missing Component                     | Impact                                                                                                                                                                                              |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Grammar normalization to PNF**      | Cannot identify Kleene-star/plus/optional nodes, so cannot use the efficient ddmin-on-children strategy for list-like constructs. Every node is treated as a regular rule node.                     |
| **BoundedBFS with subsume relation**  | `unwrap_compatible_kinds()` only matches exact kind equality. Cannot replace a node with a compatible descendant of a different (but subsuming) type. Misses many valid reductions.                 |
| **Kleene-star dispatch**              | Statement lists, argument lists, import lists, etc. are not recognized as Kleene containers. The reducer must try to delete each child individually rather than using ddmin's logarithmic strategy. |
| **Grammar-based node classification** | Without PNF, the reducer cannot distinguish between nodes that can be deleted (Kleene children), nodes that can be unwrapped (regular rules), and nodes that need special treatment.                |

**Consequence:** theseus-ship will be significantly slower and produce larger
results than a full Perses implementation on programs with many list-like
constructs (which is most real code).

### 4.2 Performance Gaps

| Issue                                                        | Detail                                                                                                                                                                                      | Potential Fix                                                                                                                                       |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Full reparse on every candidate**                          | `apply_transform` reparses the entire source for every candidate, even when the candidate is a small leaf node. For a 1000-node tree, this means 1000 full reparses per fixpoint iteration. | Use tree-sitter's incremental parsing (`parser.parse(old_tree, new_bytes)`) to reparse only the changed region. tree-sitter supports this natively. |
| **Regenerate all candidates after every accepted transform** | After accepting one transform, the entire candidate list is discarded and regenerated from scratch.                                                                                         | Maintain an incremental candidate set. When a node is deleted, only its ancestors and siblings need candidate regeneration.                         |
| **No parallel interestingness testing**                      | `jobs` parameter exists but is ignored — all tests run sequentially.                                                                                                                        | Use `concurrent.futures.ProcessPoolExecutor` to run multiple interestingness tests in parallel. C-Reduce and Shrinkray both do this effectively.    |
| **Python `hash()` for cache keys**                           | Python's `hash()` is randomized per session (PYTHONHASHSEED), so the cache is session-local only. Also has collision risk.                                                                  | Use `hashlib.sha256(source).digest()` or a faster hash like `xxhash` for deterministic, collision-resistant caching.                                |
| **`shlex.split()` called on every test invocation**          | In `_is_interesting_command`, the command string is re-parsed every time.                                                                                                                   | Cache the parsed command list once in the constructor. (Already noted in commit `4019f77` but the fix is incomplete.)                               |
| **No early termination on large subtrees**                   | If the entire program is interesting, the reducer tries to delete the root's children one by one.                                                                                           | Consider binary-search-style deletion for large node sets (ddmin's approach).                                                                       |

### 4.3 Feature Gaps (vs. State of the Art)

| Feature                                                                      | Present in                                                                    | Missing from theseus-ship |
| ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------- |
| **Scope-aware transforms** (identifier unification, dead definition removal) | bonsai                                                                        | Stub only                 |
| **Multi-language support**                                                   | C-Reduce (C/C++), Shrinkray (C, Python, JSON, CNF), bonsai (Python, JS, Rust) | Python only               |
| **Token-level reduction**                                                    | T-Rec                                                                         | Not implemented           |
| **Escaping 1-minimality**                                                    | Vulcan                                                                        | Not implemented           |
| **Incremental parsing**                                                      | tree-sitter supports it; bonsai likely uses it                                | Not used (full reparse)   |
| **Binary/non-text formats**                                                  | Shrinkray                                                                     | Not supported             |
| **Streaming/interactive reduction**                                          | Shrinkray (live UI)                                                           | Batch only                |
| **Grammar-guided fuzzing**                                                   | bonsai (in progress)                                                          | Not implemented           |

---

## 5. Recommended Improvements

### 5.1 High Impact, Moderate Effort

1. **Use incremental parsing.** tree-sitter's
   `parser.parse(old_tree, new_bytes)` avoids rewalking the entire tree. This
   alone could reduce per-candidate cost by 10–100x for small changes. This is
   the single highest-impact performance improvement.

2. **Implement BoundedBFS with the subsume relation.** The current
   `unwrap_compatible_kinds()` is too restrictive. The subsume relation
   (`B <: A` if B can be derived from A) is the key to finding valid replacement
   candidates. Without it, many valid unwrap candidates are missed.

3. **Classify Kleene nodes.** Even without full PNF normalization, heuristic
   detection of list-like constructs (nodes whose children are all the same
   type, or whose grammar rule has `*`/`+`/`?` annotations) would enable
   ddmin-based child deletion, which is O(n log n) instead of O(n²).

4. **Implement parallel testing.** The `jobs` parameter already exists. Using
   `ProcessPoolExecutor` to run N interestingness tests concurrently would give
   near-linear speedup for CPU-bound tests.

5. **Fix the unwrap transform.** The current implementation constructs child
   `NodeInfo` objects with zero byte offsets, which likely produces incorrect
   results. The child's byte range should be computed from the parent's source
   bytes using the tree-sitter node's actual offsets.

### 5.2 Medium Impact, Lower Effort

6. **Deduplicate the cache implementation.** `_Cache` in `reducer.py` and
   `ShrinkCache` in `shrink.py` are identical. Extract to a shared module.

7. **Add progress reporting.** Print current size, reduction rate, tests run,
   and elapsed time. Shrinkray's live UI is a good model.

8. **Support more tree-sitter grammars.** The architecture is extensible —
   adding a language requires only adding an extension mapping and grammar
   import. JavaScript, TypeScript, Rust, Go, and C are high-value targets.

9. **Implement the `--strict` flag.** bonsai has a `--strict` mode that rejects
   any parse errors, even pre-existing ones. Theseus-ship's error-tolerant mode
   is the default, but a strict mode would be useful for clean inputs.

10. **Cache the parsed command list.** Move `shlex.split(self._test_command)` to
    the constructor.

### 5.3 High Impact, Higher Effort

11. **Implement PNF normalization.** This is the core of Perses's theoretical
    contribution. It would require parsing tree-sitter's grammar definitions and
    applying Algorithms 1–4 from the paper. This is significant work but would
    bring theseus-ship to full Perses parity.

12. **Implement Vulcan-style escape transforms.** Escaping 1-minimality requires
    mutations that are not strictly "smaller" but enable further reduction
    (e.g., renaming a variable to a shorter name, simplifying an expression).
    This would produce measurably smaller results.

13. **Implement T-Rec-style token reduction.** After tree-level reduction
    reaches a fixpoint, a token-level pass could further reduce within nodes
    (e.g., removing unused import names, shortening identifiers).

14. **Add a Shrinkray backend mode.** Instead of the current `shrink` subcommand
    that reimplements the reducer, implement theseus-ship as a Shrinkray
    plugin/format handler. This would give it access to Shrinkray's parallelism
    and UI for free.

### 5.4 Research Directions

15. **Incremental interestingness testing.** If the interestingness test is
    itself a program analysis (e.g., "does this still crash the compiler?"),
    incremental techniques could avoid re-running the full analysis. For
    example, caching type-check results for unchanged subtrees.

16. **Machine-guided reduction.** Use a lightweight model to predict which
    candidates are most likely to be accepted, prioritizing them in the queue.
    This could significantly reduce the number of test invocations.

17. **Grammar-aware token reduction.** Combine T-Rec's token-level insight with
    Perses's grammar awareness to reduce within nodes while maintaining
    syntactic validity.

18. **Cross-language reduction.** For polyglot inputs (e.g., a Python file that
    embeds C via a build system), reduce across language boundaries
    simultaneously.

---

## 6. Comparison Matrix

| Tool             | Language               | Algorithm                   | Syntax-Guarantee | Parallel      | Minimality                  | Dependencies      |
| ---------------- | ---------------------- | --------------------------- | ---------------- | ------------- | --------------------------- | ----------------- |
| **ddmin**        | Any                    | Binary search on partitions | None             | Optional      | 1-minimal                   | None              |
| **HDD**          | Any                    | Hierarchical ddmin          | None             | Optional      | 1-minimal                   | Parser            |
| **C-Reduce**     | C/C++ (+ others)       | 80+ transformation passes   | Partial          | Yes (N cores) | Beyond 1-minimal            | Clang, Perl       |
| **Shrinkray**    | Multiformat            | Generic + format passes     | None             | Yes           | 1-minimal                   | Python 3.12+      |
| **Perses**       | Any (grammar-required) | Priority queue + BoundedBFS | Yes (every step) | No            | 1-tree-minimal              | Grammar, parser   |
| **bonsai**       | Python, JS, Rust       | Perses via tree-sitter      | Yes (every step) | Yes           | 1-tree-minimal              | tree-sitter       |
| **theseus-ship** | Python                 | Simplified Perses           | Yes (every step) | No            | 1-tree-minimal (simplified) | tree-sitter       |
| **Vulcan**       | Any (grammar-required) | Perses + escape transforms  | Yes (every step) | No            | Beyond 1-tree-minimal       | Grammar, parser   |
| **T-Rec**        | Any                    | Token-level Perses          | Yes (every step) | No            | Beyond 1-tree-minimal       | Tokenizer, parser |

---

## 7. Conclusion

**theseus-ship occupies a specific niche:** it is the most accessible Python
implementation of syntax-guided reduction, with a clean codebase, minimal
dependencies, and Python-native interestingness testing. It is not novel as an
algorithm — it is a faithful (if simplified) reimplementation of Perses — but
its design choices make it the easiest Perses implementation to adopt for
Python-centric workflows.

The most impactful improvements, in priority order:

1. **Incremental parsing** (10–100x speedup per candidate)
2. **BoundedBFS with subsume relation** (many more valid reductions found)
3. **Kleene-node classification** (ddmin on list children, O(n log n) vs O(n²))
4. **Parallel testing** (near-linear speedup with CPU-bound tests)
5. **Multi-language support** (leverage tree-sitter's 300+ grammars)

With these changes, theseus-ship could become the go-to Python-native program
reducer — combining Perses's theoretical guarantees with Python's accessibility
and tree-sitter's language coverage.

---

## References

1. Zeller, A., Hildebrandt, R. (2002). Simplifying and Isolating
   Failure-Inducing Input. _IEEE Trans. Softw. Eng._ 28(2).
2. Misherghi, G., Su, Z. (2006). HDD: Hierarchical Delta Debugging. _ICSE '06_.
3. Regehr, J. et al. (2012). Test-case reduction for C compiler bugs. _PLDI
   '12_.
4. Sun, C., Li, Y., Zhang, Q., Gu, T., Su, Z. (2018). Perses: Syntax-Guided
   Program Reduction. _ICSE '18_. DOI: 10.1145/3180155.3180236.
5. Xu, Z., Tian, Y., Zhang, M., Zhao, G., Jiang, Y., Sun, C. (2023). Pushing the
   Limit of 1-Minimality of Language-Agnostic Program Reduction (Vulcan).
   _OOPSLA '23_. DOI: 10.1145/3586049.
6. Xu, Z., Tian, Y., Zhang, M., Zhang, J., Liu, P., Jiang, Y., Sun, C. (2025).
   T-Rec: Fine-Grained Language-Agnostic Program Reduction Guided by Lexical
   Syntax. _TOSEM_ 34(2). DOI: 10.1145/3690631.
7. nnunley. bonsai: Syntax-guided test case reducer.
   https://github.com/nnunley/bonsai
8. csmith-project. C-Reduce. https://github.com/csmith-project/creduce
9. DRMacIver. Shrink Ray. https://github.com/DRMacIver/shrinkray
