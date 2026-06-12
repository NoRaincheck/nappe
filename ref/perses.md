# Perses: Syntax-Guided Program Reduction

**Authors**: Chengnian Sun, Yuanbo Li, Qirun Zhang, Tianxiao Gu, Zhendong Su\
**Venue**: ICSE '18: 40th International Conference on Software Engineering\
**DOI**: https://doi.org/10.1145/3180155.3180236

---

## Abstract

Given a program P that exhibits a certain property ψ (e.g., a C program that
crashes GCC when it is being compiled), the goal of program reduction is to
minimize P to a smaller variant P' that still exhibits the same property, i.e.,
ψ(P'). Program reduction is important and widely demanded for testing and
debugging.

This paper presents Perses, a novel framework for effective, efficient, and
general program reduction. The key insight is to exploit, in a general manner,
the formal syntax of the programs under reduction and ensure that each reduction
step considers only smaller, syntactically valid variants to avoid futile
efforts on syntactically invalid variants.

**Key Results**:

- Perses's results are respectively 2% and 45% in size of those from DD and HDD
- Perses takes 23% and 47% time taken by DD and HDD respectively
- Compared to C-Reduce, Perses takes only 38-60% reduction time

---

## 1. Introduction

Program reduction is important and widely used. Given a program P that exhibits
a property, the objective of program reduction is to generate a smaller program
P' from P that still exhibits the same property.

**Search Space Partitioning**:

Program reduction searches for suitable programs in a search space P, which can
be partitioned into:

- **P_valid**: the set of syntactically valid programs
- **P_invalid**: the set of syntactically invalid programs

```
P = P_invalid ∪ P_valid
```

**Perses Advantages**:

1. **P_invalid = ∅**: Perses can determine whether a tree node is deletable,
   avoiding generating variants by deleting undeletable nodes
2. **Enlarging P_valid**: Perses leverages grammar to support advanced program
   transformations

---

## 2. Motivating Example

### Example Program (Figure 1a)

```c
int main() {
  int a = 1;
  if (a) {
    printf("%d\n", a);
    printf("Hello ");
    printf("world!\n");
    printf("End\n");
  }
  return 0;
}
```

### Reduction Steps

1. **Step 1 (1.func_def)**: Cannot remove root, add children to queue
2. **Step 2 (2.compound_stmt)**: Cannot delete, replace with descendant fails
   (undefined 'a')
3. **Step 3 (3.stmt_star)**: Kleene-Star node, use DD to delete children
4. **Step 4 (4.if_stmt)**: Replace with child `6.compound_stmt` (the true
   branch)
5. **Step 5 (5.compound_stmt)**: Replace with descendant `6.stmt_star`
6. **Step 6 (6.stmt_star)**: Kleene-Star node, use DD to remove irrelevant
   children

### Final Result (Figure 1d)

```c
int main() {
  int a = 1;
  if (a) {
    printf("Hello ");
    printf("world!\n");
  }
  return 0;
}
```

---

## 3. Preliminaries

### 3.1 Program Reduction

**Property Test Function**: ψ : P → B, where B = {true, false}

**Goal**: Find minimized program p ∈ P such that ψ(p) ∧ |p| < |P|

**Ideal Goal**:

```
arg min  |p| ≡ {p | p ∈ P ∧ ψ(p) ∧ ∀x ∈ P. |p| ≤ |x|}
p∈P∧ψ(p)
```

**Minimality Definitions**:

- **1-minimality**: p is 1-minimal if any variant p' derived by removing a
  single element fails ψ
- **1-tree-minimality**: Any node of the tree representation cannot be further
  simplified

### 3.2 Delta Debugging Algorithm (ddmin)

**Input**: List L of elements, property ψ

**Algorithm**:

1. **Split Phase**: Split L into n partitions. For each partition u, test if u
   alone preserves ψ. If yes, remove complement.
2. **Complement Phase**: Test if complement of each partition preserves ψ. If
   yes, remove u.
3. **Split Phase (refine)**: Try to split each remaining partition into halves
   (n → 2n). Resume at Step 1.

**Termination**: When each partition cannot be further split, remaining elements
are the reduced result.

### 3.3 Grammar Quantifiers

Perses supports three quantifiers over terminals and nonterminals:

| Quantifier  | Symbol | Description              | Example                |
| ----------- | ------ | ------------------------ | ---------------------- |
| Kleene Star | `*`    | Zero or more occurrences | A* → ε, 'A', 'AA', ... |
| Kleene Plus | `+`    | One or more occurrences  | A+ → 'A', 'AA', ...    |
| Optional    | `?`    | Zero or one occurrence   | A? → ε or 'A'          |

**Quantifiable Nonterminal**: A nonterminal A is quantifiable if A could be
transitively described by a quantified rule.

---

## 4. Approach

### 4.1 Perses Normal Form (PNF)

**Definition 3.1**: A context-free grammar CFG is in PNF if all production rules
are of the form:

1. `A → B₁ B₂ ... Bₙ` (regular rule)
2. `A → B₁*` (Kleene Star)
3. `A → B₁+` (Kleene Plus)
4. `A → B₁?` (Optional)
5. `S → ε` (epsilon rule for start symbol)

Where:

- S is the start symbol
- A is a nonterminal
- Bᵢ is either a terminal or nonterminal
- n > 1
- All quantifiable nonterminals are transitively described by at least one
  quantified rule

### PNF Normalization Algorithm (Algorithm 1)

```
Algorithm 1: PNF Normalization — Normalization(G)
  Input: G: a context-free grammar in BNF notation
  Output: G': an equivalent grammar in PNF

1 Preprocess(G)
2 G₁ ← GrammarNormalizationLeft(G)
3 G' ← GrammarNormalizationRight(G₁)
4 return G'
```

#### GrammarNormalizationLeft(G)

```
Function GrammarNormalizationLeft(G):
  Input: G: a context-free grammar in BNF notation
  Output: G: equivalent grammar without quantifiable nonterminals in left recursion form

6  let G_cfg be an empty digraph
7  foreach Nᵢ → Nⱼ α do G_cfg ← G_cfg ∪ {(Nᵢ, Nⱼ)}
8  SCC ← Compute_SCC(G_cfg)
9  foreach sccᵢ ∈ SCC do
10    Gᵢ ← ∅
11    foreach A ∈ sccᵢ do insert all rules of the form A → α to Gᵢ
12    G'ᵢ ← GrammarTransformationLeft(Gᵢ)
13    G'ᵢ ← QuantifierIntroductionLeft(G'ᵢ)
14    G ← (G \ Gᵢ) ∪ G'ᵢ
15  return G
```

#### GrammarTransformationLeft(G)

```
Function GrammarTransformationLeft(G):
  Input: G: a context-free grammar in BNF notation
  Output: G: equivalent grammar with direct left recursion

17 foreach nonterminal Nᵢ ∈ G do
18   repeat
19     foreach rule Nᵢ → Nⱼ αᵢ ∈ G do
20       if j < i then
21         remove Nᵢ → Nⱼ αᵢ from G
22         foreach rule Nⱼ → αⱼ ∈ G do
23           add Nᵢ → αⱼ αᵢ to G
24   until Grammar G remains unchanged
25 return G
```

#### QuantifierIntroductionLeft(G)

```
Function QuantifierIntroductionLeft(G):
  Input: G: a context-free grammar in BNF notation
  Output: G: equivalent grammar with quantifiers

27 foreach nonterminal Nᵢ ∈ G do
28   StarIntroductionLeft(G, Nᵢ)
29   foreach Nᵢ → α₁ α' (α')* α₂ do
30     remove Nᵢ → α₁ α' (α')* α₂ from G
31     let U₁, U₂ be new auxiliary nonterminals
32     G ← G ∪ {Nᵢ → α₁ U₁ α₂, U₁ → U₂+, U₂ → α'}
33   foreach pair of (Nᵢ → αᵢ, Nᵢ → αⱼ), where |αᵢ| ≤ |αⱼ| do
34     if αⱼ = α₁ α' α₂ and αᵢ = α₁ α₂ then
35       remove Nᵢ → αᵢ and Nᵢ → αⱼ from G
36       let U₃, U₄ be new auxiliary nonterminals
37       G ← G ∪ {Nᵢ → α₁ U₃ α₂, U₃ → U₄?, U₄ → α'}
38 return G
```

#### StarIntroductionLeft(G, N)

```
Function StarIntroductionLeft(G, N):
  Input: G: a set of grammar productions
  Input: N: a nonterminal
  Output: G: a set of grammar productions with *-quantified rules

40 A ← ∅ and B ← ∅
41 foreach rule N → α ∈ G do
42   if α = N α₁ then A ← A ∪ {α₁}
43   else B ← B ∪ {α}
44   remove N → α from G
45 foreach bᵢ ∈ B do
46   denote set A as {a₁, a₂, ..., aⱼ}
47   let U₁, U₂ be new auxiliary nonterminals
48   G ← G ∪ {N ← bᵢ U₁, U₁ → U₂*, U₂ → a₁ | a₂ | ... | aⱼ}
49 return G
```

---

### 4.2 Main Reduction Algorithm

```
Algorithm 2: The Main Algorithm — Reduce(P, ψ)
  Input: P: the program to be reduced
  Input: ψ: P → B: the property to be preserved
  Output: A minimum program p ∈ P s.t. ψ(p)

1 best ← ParseTree(P)
2 worklist ← {RootNode(best)}
3 while |worklist| > 0 do
4   largest ← GetAndRemoveLargestFrom(worklist)
5   if largest is Kleene-Star Node then
6     (best, pending) ← ReduceStar(best, ψ, largest)
7   else if largest is Kleene-Plus Node then
8     (best, pending) ← ReducePlus(best, ψ, largest)
9   else if largest is Optional Node then
10    (best, pending) ← ReduceStar(best, ψ, largest)
11  else if largest is Regular Rule Node then
12    (best, pending) ← ReduceRegular(best, ψ, largest)
13  else continue // Skip token nodes
14  worklist ← worklist ∪ pending
15 return best
```

---

### 4.3 Reducing Quantified Nodes

#### ReduceStar (Algorithm 3)

```
Algorithm 3: ReduceStar(tree, ψ, node)
  Input: tree: the parse tree to be reduced
  Input: ψ: P → B: the property to be preserved
  Input: node: the parse tree node to be reduced
  Output: (best, pending): best is the minimum tree, pending is remaining descendants

1 all ← Children(node)
2 remaining ← ddmin(all, ψ)
3 best ← tree.CopyAndRemove(all \ remaining)
4 return (best, remaining)
```

**Key Points**:

- Kleene-Star and Optional nodes are treated the same way
- Uses ddmin to delete irrelevant children
- Each child is independent in terms of syntax validity

#### ReducePlus

Similar to ReduceStar, but maintains constraint: at least one child must remain
(enforced by Kleene-Plus semantics).

---

### 4.4 Reducing Regular Rule Nodes

```
Algorithm 4: ReduceRegular(tree, ψ, node)
  Input: tree: the parse tree to be reduced
  Input: ψ: P → B: the property to be preserved
  Input: node: the parse tree node to be reduced
  Output: (best, pending): best is the minimum tree, pending is remaining descendants

1 candidates ← ∅
2 begin searching for replacement candidates
3   subsume_pred ← λn. Rule(n) <: ExpectedRule(node)
4   replacement_candidates ← BoundedBFS(node, subsume_pred, 4)
5   candidates ← candidates ∪ replacement_candidates

6 if IsKleene(Parent(node)) then
7   kleene_pred ← λn. IsKleene(n) ∧ QuantifiedRule(n) <: ExpectedRule(node)
8   quantified_candidates ← BoundedBFS(node, kleene_pred, 4)
9   candidates ← candidates ∪ quantified_candidates

10 best ← node
11 foreach c ∈ candidates do
12   t ← tree.CopyAndReplace(node, c)
13   if ψ(t) ∧ |t| < |tree.CopyAndReplace(node, best)| then
14     best ← {c}

15 if best = node then return (tree, Children(node))
16 else return (tree.CopyAndReplace(node, best), best)
```

#### Subsume Relation (Definition 4.1)

Given two symbols A and B (terminals or non-terminals):

- **B <: A** if:
  - A = B, or
  - B can be derived from A

Examples:

- `stmt <: stmt` (reflexive)
- `if_stmt <: stmt` (if_stmt can be derived from stmt)

#### Auxiliary Functions

- **Rule(n)**: Returns the production rule that creates node n
- **ExpectedRule(n)**: Returns the expected production rule at the position of n
  in its parent's context
- **QuantifiedRule(n)**: For Kleene nodes, returns the quantified production
  rule

#### BoundedBFS

```
Function BoundedBFS(node, pred, max_depth):
  Input: node: the starting node of breadth-first search
  Input: pred: TreeNodes → B: predicate to match tree nodes
  Input: max_depth: depth bound
  Output: result: the matched tree nodes

18 Queue queue ← Children(node)
19 result ← ∅
20 while |queue| > 0 ∧ max_depth > 0 do
21   max_depth ← max_depth − 1
22   queue_size ← |queue|
23   for i ← 0 to queue_size do
24     n ← Dequeue(queue)
25     if pred(n) then
26       result ← result ∪ {n}
27       continue;
28     if max_depth > 0 then
29       foreach c ∈ Children(n) do Enqueue(queue, c)
30 return result
```

**Constraints on path L between node and compatible node n**:

1. Number of nodes in L is bounded
2. No other compatible node on L before n (n is the first compatible node)

---

### 4.5 Fixpoint Reduction Mode

A single run of Reduce does not guarantee 1-tree-minimality because deletion of
one node may enable deletion of another.

**Solution**: Repeatedly apply Reduce until no more tree nodes can be removed.
The final result will be 1-tree-minimal.

---

## 5. Evaluation

### 5.1 C Programs

**Benchmark**: 20 C programs triggering bugs in GCC and Clang

**Tools Compared**:

- Delta (line-based DD)
- MultiDelta (block-aware DD)
- DeltaF (Delta in fixpoint mode)
- C-Reduce (C/C++ specialized)
- HDD (Hierarchical DD)
- HDDF (HDD in fixpoint mode)
- Perses
- PersesF (Perses in fixpoint mode)

**Results**:

| Metric | Perses vs Others              |
| ------ | ----------------------------- |
| Size   | 55-98% smaller than DD/HDD    |
| #tests | 47-93% fewer property tests   |
| Time   | 34-77% shorter reduction time |
| Speed  | 1.1-2.6x faster               |

### 5.2 Java Programs

**Benchmark**: 6 Java programs triggering bugs in Javac and Eclipse Compiler for
Java

**Results**: Perses outperforms HDD:

- 2.07x faster
- 1.13x smaller results
- 3.99x fewer queries

---

## Key Implementation Concepts

### Priority Queue

- Stores tree nodes for reduction
- Retrieves node with most tokens first
- Children added after node reduction

### Node Types

1. **Kleene-Star**: Zero or more children, use DD
2. **Kleene-Plus**: One or more children, use DD with constraint
3. **Optional**: Zero or one child, treat as Kleene-Star
4. **Regular Rule**: Replace with compatible descendant

### Compatibility Rules

- **Regular nodes**: Rule(n) <: ExpectedRule(node)
- **Kleene nodes**: IsKleene(n) ∧ QuantifiedRule(n) <: ExpectedRule(node)

### Grammar Normalization

1. Preprocessing: Remove ε-productions, unreachable rules
2. Transformation: Convert to left/right recursion
3. Normalization: Introduce quantifiers (star, plus, optional)

---

## Grammar Example (Figure 2)

```
func_def    ::= type identifier '(' ')' compound_stmt
stmt        ::= if_stmt | decl_stmt | expr_stmt | compound_stmt
if_stmt     ::= cond_plus decl_stmt | cond_plus expr_stmt | cond_plus compound_stmt
cond_plus   ::= if_cond+
if_cond     ::= 'if' '(' expr ')'
decl_stmt   ::= type identifier '=' expr ';'
expr_stmt   ::= expr ';'
compound_stmt ::= '{' stmt_star '}'
stmt_star   ::= stmt*
```

---

## References

1. Aho, A.V., Sethi, R., Ullman, J.D. (1986). Compilers: Principles, Techniques,
   and Tools. Addison-Wesley.
2. ANTLR. (2017). http://www.antlr.org/
3. Binkley, D. et al. (2014). ORBS: language-independent program slicing. In
   FSE.
4. GCC. (2017). A Guide to Testcase Reduction.
   https://gcc.gnu.org/wiki/A_guide_to_testcase_reduction
5. Hoare, T. (2003). The verifying compiler: A grand challenge for computing
   research. In Modular Programming Languages.
6. IBM. (2017). The T.J. Watson Libraries for Analysis.
   http://wala.sourceforge.net/
7. JavaCC. (2017). https://javacc.org/
8. JS Delta. (2017). https://github.com/wala/jsdelta
9. Le, V., Afshari, M., Su, Z. (2014). Compiler Validation via Equivalence
   Modulo Inputs. In PLDI.
10. Le, V., Sun, C., Su, Z. (2014). Randomized Stress-Testing of Link-Time
    Optimizers. In ISSTA.
11. Le, V., Sun, C., Su, Z. (2015). Finding Deep Compiler Bugs via Guided
    Stochastic Program Mutation. In OOPSLA.
12. Lekies, S. et al. (2013). 25 million flows later: large-scale detection of
    DOM-based XSS. In CCS.
13. LLVM. (2017). How to submit an LLVM bug report.
    https://llvm.org/docs/HowToSubmitABug.html
14. LLVM/Clang. Clang documentation – LibTooling.
    https://clang.llvm.org/docs/LibTooling.html
15. McPeak, S., Wilkerson, D.S., Goldsmith, S. Berkeley Delta.
    http://delta.tigris.org/
16. Misherghi, G., Su, Z. (2006). HDD: Hierarchical Delta Debugging. In ICSE.
17. Regehr, J. et al. (2012). Test-case reduction for C compiler bugs. In PLDI.
18. Herfert, J.P.S., Pradel, M. (2017). Automatically Reducing Tree-Structured
    Test Inputs. In ASE.
19. Saxena, P. et al. (2010). FLAX: Systematic Discovery of Client-side
    Validation Vulnerabilities. In NDSS.
20. Sun, C., Le, V., Su, Z. (2016). Finding compiler bugs via live code
    mutation. In OOPSLA.
21. Sun, C., Le, V., Zhang, Q., Su, Z. (2016). Toward Understanding Compiler
    Bugs in GCC and LLVM. In ISSTA.
22. Yang, X. et al. (2011). Finding and understanding bugs in C compilers. In
    PLDI.
23. Yoo, S. et al. (2014). Seeing Is Slicing: Observation Based Slicing of
    Picture Description Languages. In SCAM.
24. Zeller, A., Hildebrandt, R. (2002). Simplifying and Isolating
    Failure-Inducing Input. IEEE Trans. Softw. Eng. 28(2).
25. Zhang, Q. et al. (2017). Skeletal program enumeration for rigorous compiler
    testing. In PLDI.
