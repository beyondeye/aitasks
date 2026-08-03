---
Task: t1384_syncer_inherited_test_dup_guard.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# t1384 — Structural guard against inherited test duplication

## Context

t1354_4 found that `TabbedShellTests` in `tests/test_syncer_rows.py` defined 25
test methods **and** served as the helper base for three subclasses. unittest and
pytest both collect inherited test methods, so each subclass silently re-ran all
25 — **75 duplicate `SyncerApp` boots, ~46s, about half that file's runtime**,
testing nothing the base run had not already covered. Every duplicate passed, so
the defect was invisible for as long as it existed.

t1354_4 fixed that one instance (extract a test-free `_TabbedShellBase`, keep the
tests in a concrete `TabbedShellTests`, re-point the other three suites at the
base). Nothing prevents the next one. This task adds the structural guard.

**Premise verified before planning** (read-only AST sweep run against the live
tree): 183 `tests/test_*.py` files, 166 in-module inheritance edges evaluated,
**0 violations**. So the guard ships reporting zero with an allowlist that is
empty by design — and it is not vacuous, because it reaches 166 real decision
points.

**Two corrections to the task text**, established during exploration:

1. *"Reuse the AST scan written during t1354_4 planning"* — that scan was never
   persisted. `aiplans/archived/p1354/p1354_4_retrospective_measure.md` only
   *describes* it in prose (lines 92-107, 124-127); there is no code block. The
   scanner is written from scratch here.
2. *"the related-but-distinct t1375 guard"* — t1375 is **`status: Ready`, never
   implemented**. No `bare_module_test_fn_guard` exists. The only guard that
   currently catches a module-level `def test_*` is `tests/test_collection_parity.py`
   (t1354_3), which is `skipUnless(pytest importable)` and therefore inert on a
   default install — which is exactly why t1375 was filed.

Given (2), the "do they belong in one module?" question is live, and the answer
(user-selected) is **yes**: this task creates the shared home and t1375 lands
its guard beside this one.

## Approach

One new file, `tests/test_collection_structure.py`, plus a one-line coordination
pointer added to t1375's task file. **No production code is touched.**

The module is a pure-AST scan: it `ast.parse`s each file's source and never
imports a test module, so it needs none of the subprocess machinery that
`tests/test_no_zero_collection.py` requires (that guard has to import siblings to
count discovery; this one does not).

### Prior art reused

| Source | What is reused |
|---|---|
| `tests/test_no_zero_collection.py:50-50` | `ZERO_COLLECTION_ALLOWLIST` — the "explicit, commented, empty by design, one-line justification per entry, NEVER a silent skip" allowlist policy, copied verbatim in spirit |
| `tests/test_no_zero_collection.py:187-283` | `GuardFalsifiabilityTests` — separate negative-control class building synthetic files in `tempfile.TemporaryDirectory()`, asserting the offender is flagged **by name** and a clean baseline is **not** |
| `tests/test_collection_parity.py:274-283` | the assertion triad: flagged by name · correct detail · `assertNotIn` on the clean file so the control cannot pass because everything is flagged |
| `tests/test_board_fixture_harness.py:432-443` | `_sweep_findings(..., allowed=None)` — the allowlist is an **injectable parameter** so a control can prove the mechanism is load-bearing rather than decorative |
| `tests/test_board_fixture_harness.py:359-361` | "structural, not substring: a docstring mentioning it must not trip the guard" — carried over as a fixture |

### The rule

For each `tests/test_*.py`: build `{name: ClassDef}` over **top-level** classes.
For each class, for each base that is an `ast.Name` resolving to a class in that
same map, count the base's **own** `test_*` members (direct `FunctionDef` /
`AsyncFunctionDef` children). Non-zero ⇒ violation.

Deliberate scope limits, stated in the docstring so they are not over-read:

- **Top-level classes only** — a class nested in a function or another class is
  not a module attribute and is not collected by either backend.
- **`ast.Name` bases only** — attribute bases (`mod.Base`) are intentionally out
  of scope. They *can* name a class in the same module, via a self-import, but
  resolving that would mean tracking import bindings; the guard declines to, and
  a control pins the limit so it reads as deliberate rather than accidental.
- **Direct edges only** — this is *detection*, not enumeration. Any chain that
  reaches a test-defining base contains a direct edge into it, so the chain is
  always flagged at that link, and the sanctioned fix resolves the whole chain.
- **Syntactic, not collection-aware** — the rule does *not* model whether either
  class is actually collected. It flags the edge purely on shape, so a hierarchy
  that no backend collects (e.g. a plain `class Base:` that is not a `TestCase`
  and is not named `Test*`, carrying a `def test_x`, plus a `class Sub(Base)`)
  is flagged even though nothing re-runs. That is the intended trade: resolving
  "is this collected?" would mean chasing base chains to `unittest.TestCase`
  through imports and attributes, which is exactly the fragility this guard is
  meant to avoid. The consequence is stated in both the docstring and the
  failure text: **a hit is normally answered with a structural refactor** (make
  the base test-free), **not with an allowlist entry** — the allowlist exists for
  a genuinely collected-but-harmless edge, which no current file has.

## Implementation

### 1. New file `tests/test_collection_structure.py`

**Module docstring** — states: what the module is for (structural, AST-only
guards over the *shape* of `tests/test_*.py`); the t1354_4 measurement that
motivates the first guard; why AST and not grep; **all four** scope limits above
— including, explicitly, that the rule is syntactic rather than collection-aware
and that a hit is normally answered by a structural refactor, not an allowlist
entry;
and a short **"Adding a guard here"** contract — each guard is one allowlist
`frozenset`, one live-tree `TestCase`, and one falsifiability `TestCase`, all
sharing `_iter_test_modules()` — naming **t1375's `bare_module_test_fn_guard` as
the next intended occupant**. No commented-out stub code.

**Module constants**

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# Explicit, commented, and empty by design — same policy as
# ZERO_COLLECTION_ALLOWLIST (tests/test_no_zero_collection.py) and
# PARITY_ALLOWLIST (tests/test_collection_parity.py). An entry is the exact
# pair key "<stem>: <Sub>(<Base>)" and needs a written justification. At t1384
# completion the live tree has zero violations, so nothing is waived.
#
# The normal answer to a hit is a STRUCTURAL REFACTOR, not an entry here: make
# the base test-free and move its tests into a concrete subclass. Waive an edge
# only when it is genuinely collected AND genuinely harmless, and say why.
INHERITED_TEST_DUP_ALLOWLIST: frozenset[str] = frozenset()
```

The allowlist key is the **stable pair** `"<stem>: <Sub>(<Base>)"` — not the full
message, which embeds a method count that would make an entry go stale the next
time a test is added to the base.

**Helpers** (module-private, shared by future guards)

- `_iter_test_modules(tests_dir)` → yields `(stem, source, tree)` for every
  `test_*.py`, sorted. **Fail-closed:** `ast.parse` raising `SyntaxError` is
  converted to an `AssertionError` whose message names the offending file —
  never caught-and-skipped, which would let an unparsable module silently drop
  out of every guard in this file. Pinned by a control (below), because an
  unexercised fail-closed branch is one refactor away from becoming a skip.
- `_own_test_methods(node: ast.ClassDef) -> list[str]` — direct `FunctionDef` /
  `AsyncFunctionDef` children whose name starts with `test_`.
- `_inherited_dup_pairs(stem, source) -> list[tuple[str, str, list[str]]]` —
  `(sub, base, base_own_tests)` per offending edge; also returns the count of
  in-module `ast.Name` base edges examined (via a small `NamedTuple`, so the
  non-vacuity floor below has real data rather than a bare boolean).
- `_scan_dir(tests_dir, allowlist=None) -> _ScanResult` — `NamedTuple(findings,
  modules, edges)`; `allowlist` defaults to `INHERITED_TEST_DUP_ALLOWLIST`.
  This is the single entry point used by **both** the live test and the
  synthetic-dir control.

**`class NoInheritedTestDuplicationTests(unittest.TestCase)`** — the live tree,
one `_scan_dir(TESTS_DIR)` in `setUpClass`:

- `test_no_class_inherits_tests_from_a_same_module_base` — `findings == []`.
  Failure message names the offending pairs and the sanctioned fix verbatim:
  extract a test-free `_PrefixedBase` holding only the helpers, keep the tests in
  a concrete subclass, re-point the other subclasses at the base (the leading
  underscore is what keeps the base out of collection — same pattern as
  `_TabbedShellBase` in `tests/test_syncer_rows.py:860`, and as
  `GitRepoTestBase` / `BrainstormCrewTestBase`). The message closes by naming
  the rule as **syntactic** — it does not check whether the classes are actually
  collected — and directs the reader to that structural refactor rather than to
  `INHERITED_TEST_DUP_ALLOWLIST`, which is a last resort needing a written
  justification.
- `test_the_scan_reached_real_inheritance_edges` — the **non-vacuity floor**:
  `modules >= 50` and `edges >= 1`. Loose floors against a broken glob or a
  wrong root, explicitly *not* pinned counts (today: 183 and 166).

**`class InheritedDupOracleFalsifiabilityTests(unittest.TestCase)`** — negative
control, never mutating a real file:

- `test_oracle_flags_the_t1354_4_shape_in_a_synthetic_tests_dir` — writes two
  real files into a `TemporaryDirectory`, runs them through `_scan_dir` (the same
  entry point the live test uses, per the real-entry-point rule):
  - `test_offender.py`: `class Base(unittest.TestCase)` with its own `test_a` /
    `test_b`, plus `class Sub(Base)`.
  - `test_clean.py`: the sanctioned shape — test-free `class _Helper(unittest.TestCase)`
    plus `class Real(_Helper)` holding the tests.

  Asserts the offender is flagged **by file and class pair by name**
  (`"test_offender"` and `"Sub(Base)"` both present in the joined findings),
  `"test_clean"` is **not** present, and `modules == 2 and edges == 2` — which is
  what proves the edge counter behind the non-vacuity floor is real.
- `test_oracle_discriminates_on_each_scope_boundary` — in-memory battery over
  `_inherited_dup_pairs`, one `subTest` per fixture:

  | fixture | expect |
  |---|---|
  | base with `def test_x` + subclass | **flagged** |
  | base with `async def test_x` + subclass | **flagged** (pins `AsyncFunctionDef`) |
  | `C` has tests, `B(C)`, `A(B)` | **flagged**, and specifically at the `B(C)` edge |
  | test-free `_Base` + two concrete subclasses (the t1354_4 fix) | not flagged |
  | `from x import Base` + `class Sub(Base)` | not flagged (base not in module) |
  | in-module `Base` with tests **and** `class Sub(m.Base)` | not flagged — pins that `ast.Attribute` bases are out of scope even when the name collides |
  | base whose **docstring** contains the literal text `def test_x` | not flagged (AST, not grep) |
  | test-defining base declared **inside a function** + subclass | not flagged (top-level only) |
  | plain `class Base:` (no `TestCase`, not named `Test*`) with `def test_x` + `class Sub(Base)` | **flagged** — pins the *known* false positive as deliberate: the rule is syntactic, so an uncollected hierarchy still trips it. A refactor that quietly made the scan collection-aware would break this fixture and have to justify itself. |

- `test_scan_fails_closed_on_an_unparsable_module` — writes
  `test_broken_syntax.py` containing `class Base(:` into a `TemporaryDirectory`
  alongside one valid module, then asserts `_scan_dir` **raises**
  `AssertionError` with `"test_broken_syntax"` in the message. Without this, the
  fail-closed branch is never executed by any test, and a later refactor could
  swap it for a `except SyntaxError: continue` — letting a broken module drop out
  of the scan while every other assertion here stayed green.

- `test_allowlist_entry_suppresses_exactly_the_pinned_pair` — proves the
  allowlist mechanism is load-bearing despite shipping empty: re-runs the
  synthetic offender with `allowlist={"test_offender: Sub(Base)"}` (findings
  empty) and again with the near-miss `{"test_offender: Sub(Other)"}` (still
  flagged), so the key is exact rather than substring.

**Self-consistency:** the new file's own synthetic sources live in string
literals, so the live scan (which includes this file) sees no ClassDef for them —
and its two `TestCase`s do not subclass each other. The guard passes over itself.

### 2. `aitasks/t1375_bare_module_test_fn_guard.md` — coordination pointer

Under "Suggested approach", replace the last bullet's open question about
placement with a pointer: `tests/test_collection_structure.py` (t1384) is the
shared home; reuse its `_iter_test_modules()` and follow the "Adding a guard
here" contract in its docstring; the allowlist policy bullet stays as-is.
Committed with `./ait git` (task data), separately from the code commit.

### Explicitly out of scope

- No change to `tests/run_all_python_tests.sh` — a new `tests/test_*.py` is
  discovered by both backends automatically.
- No entry added to `aidocs/framework/testing_conventions.md`. That file has no
  guard-test section today (noted in `tests/test_concern_body_display_contract.py`'s
  docstring: the convention is precedent-only); writing one is a separate change,
  and this task declares no `docs_updated` gate.
- t1375's guard is **not** implemented here — only its home is prepared.

## Verification

1. `python3 -m unittest tests.test_collection_structure -v` — all tests pass;
   the live guard reports zero violations with an empty allowlist.
2. **Negative control observed failing against the real defect**, without
   mutating any tracked file: copy `tests/` to a tmpdir, append
   `class Dup(TabbedShellTests): pass` to the *copy* of `test_syncer_rows.py`,
   run `_scan_dir` on the copy, and confirm it reports
   `test_syncer_rows: Dup(TabbedShellTests)` with 25 inherited methods — i.e. it
   reproduces exactly the shape t1354_4 removed. Output recorded in the plan's
   Final Implementation Notes.
3. `python3 -m unittest tests.test_no_zero_collection tests.test_collection_parity`
   — the new file contributes ≥1 collected test and is collected identically by
   both backends (it must not itself trip the sibling collection guards).
4. `bash tests/run_all_python_tests.sh --test-dir tests` — full Python suite;
   read **only** the last line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`).

## Step 9 — Post-Implementation

Current-branch mode: no worktree or branch to merge or clean up. Step 9 runs the
merge-approval gate against `main` (per the plan header), dispatches
`./ait gates run 1384` for the declared `risk_evaluated` gate, then archives via
`./.aitask-scripts/aitask_archive.sh 1384`.

## Risk

### Code-health risk: low

- The `ast.Name`-only base rule cannot see an in-module base reached through an
  `ast.Attribute` (`mod.Base`) or a re-binding (`Alias = Base; class Sub(Alias)`),
  so a future evasion would pass silently · severity: low · → mitigation: none —
  accepted as a documented scope limit, pinned by the `class Sub(m.Base)` control
  so the boundary reads as deliberate rather than accidental (no follow-up task;
  user declined at planning)
- The rule is syntactic, so it can flag an inheritance edge that no backend
  actually collects — a future false positive unrelated to duplicate execution ·
  severity: low · → mitigation: mitigated in-plan — the limit is stated in the
  docstring **and** the failure text, which points at a structural refactor
  rather than the allowlist, and a control fixture pins the known false-positive
  shape as deliberate
- No production code is touched and the only cost is 183 `ast.parse` calls on
  the live tree, so the blast radius is one new test file · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low

- A guard whose scan reaches nothing would pass vacuously — a broken glob or a
  wrong `TESTS_DIR` would turn a green result into no result at all · severity:
  low · → mitigation: mitigated in-plan by the `modules >= 50 and edges >= 1`
  non-vacuity floor and by the synthetic-dir control asserting `modules == 2 and
  edges == 2`
- The premise that the live tree has zero violations was measured before
  planning (183 files, 166 edges, 0 findings), so the "ships green with an empty
  allowlist" acceptance criterion is verified rather than assumed · severity:
  low · → mitigation: none needed

## Final Implementation Notes

- **Actual work done:** Created `tests/test_collection_structure.py` (483 lines)
  — a shared home for AST-only structural guards over `tests/test_*.py`, holding
  the first guard: no top-level class may subclass another top-level class in the
  same module that defines its own `test_*` methods. Shipped with
  `INHERITED_TEST_DUP_ALLOWLIST` empty by design, a live-tree `TestCase` (findings
  + a non-vacuity floor), and a falsifiability `TestCase` with four controls.
  Also settled t1375's placement into this module via a pointer in
  `aitasks/t1375_bare_module_test_fn_guard.md`.

- **Deviations from plan:** Two, both simplifications made during
  implementation.
  1. `_iter_test_modules()` yields `(stem, tree)` rather than the planned
     `(stem, source, tree)`, and the `_Module` NamedTuple was dropped. Every
     guard in this module is pure-AST (t1375's planned bare-module-`def test_*`
     check included), so the raw `source` field had no reader — shipping it
     would have been speculative generality in a shared helper.
  2. The Step-6 checkpoint's approval AskUserQuestion was not re-issued:
     `ExitPlanMode` had just collected the same approval, so re-prompting would
     have been duplicate friction. The substantive half of that branch — the
     Remote Drift Check — was still run (`main`: `UP_TO_DATE`).

- **Issues encountered:**
  - *Two review rounds before approval, both valid.* (a) The plan asserted
    `_iter_test_modules` fails closed on a `SyntaxError`, but no control created
    malformed Python — an unexercised fail-closed branch is one refactor away
    from becoming `except SyntaxError: continue`. Added
    `test_scan_fails_closed_on_an_unparsable_module`. The same reasoning was
    then applied to the allowlist, which ships empty and would otherwise never
    be exercised: `test_allowlist_entry_suppresses_exactly_the_pinned_pair` now
    proves it waives on an exact key and *not* on a near-miss key. (b) The rule
    is syntactic and does not model whether either class is actually collected,
    so it can flag an uncollected hierarchy. Documented as scope limit 4 in the
    docstring **and** in the failure text, which directs the reader to a
    structural refactor rather than an allowlist entry, with fixture
    `d_uncollected_hierarchy` pinning the known false positive as deliberate.
  - *A third review round corrected a factual claim:* "an `ast.Attribute` base is
    by definition not the same module" is false for a self-import. Reworded to
    "attribute bases are intentionally out of scope", which is what the code
    actually does.
  - *Concurrent-session interference during verification.* The first full-suite
    run failed with 2 errors in `tests/test_board_movement.py::HarnessDiscriminationTests`
    (`NameError: name 'atomic_write_text' is not defined`), raised inside the
    board during a Textual `run_test`. Another session was mid-flight on an
    atomic-write migration touching `.aitask-scripts/board/aitask_board.py`
    (255 uncommitted insertions) and had the import momentarily absent at the
    instant the suite imported it. Re-running those tests directly a few minutes
    later passed, and a full re-run of the suite passed outright — so it was a
    transient snapshot of concurrent work, not a broken commit.
  - *A detached `git worktree` at HEAD is NOT a valid surface for this suite.*
    Used as a cross-check, it produced 4 unrelated failures
    (`test_profile_editor_shadow_tier.py`, `test_settings_brainstorm_descriptions.py`,
    `test_board_movement.py::IsolationNegativeControlTests`) purely because
    `aitasks/` is a symlink into the `.aitask-data` worktree, which such a
    checkout does not have — the link dangles and every metadata-reading test
    fails. Evidence discarded; the worktree was removed. Worth remembering
    before reaching for that technique again in this repo.

- **Key decisions:**
  - *Shared module over a narrow one.* t1375 is still `Ready` and unimplemented,
    so its placement was genuinely open. `tests/test_collection_structure.py`
    is named for the concern (structural properties of what the tests tree
    collects) rather than this one defect, its docstring carries an "Adding a
    guard here" contract (one allowlist + one live `TestCase` + one
    falsifiability `TestCase`, sharing `_iter_test_modules()`), and t1375's task
    file now points at it. No commented-out stub code was left behind.
  - *Allowlist key excludes the method count.* The key is
    `"<stem>: <Sub>(<Base>)"`; the count lives only in the message. Embedding it
    would silently un-waive an entry the next time a test was added to the base.
  - *Rich returns over booleans.* `_scan_dir` returns
    `(findings, modules, edges)` so the live test can assert the sweep reached
    its decision points — a scan that found no files reports "no violations",
    which reads identically to a clean tree. Floors are loose
    (`modules >= 50`, `edges >= 1`), deliberately not pinned counts.
  - *Direct edges only.* Detection, not enumeration: any chain reaching a
    test-defining base contains a direct edge into it, so the chain is always
    flagged at that link and the structural fix resolves it wholesale. Fixture
    `c_transitive` pins this.

- **Upstream defects identified:** None.

- **Verification evidence:**
  - `python3 -m unittest tests.test_collection_structure` — 6 tests, OK (~0.5s).
  - Live tree, empty allowlist: **0 findings** over 185 modules and 169
    in-module inheritance edges (the guard is not vacuous — it reaches 169 real
    decision points).
  - **Negative control against the real defect**, no tracked file mutated: copied
    `tests/*.py` to a tmpdir, appended `class Dup(TabbedShellTests): pass` to the
    *copy* of `test_syncer_rows.py`, and re-scanned. Live `findings=0 edges=169`
    → mutated `findings=1 edges=170`, reporting
    `test_syncer_rows: Dup(TabbedShellTests) re-runs 25 inherited test_* method(s)
    defined on TabbedShellTests` — 25 being exactly the figure t1354_4 measured.
  - `python3 -m unittest tests.test_no_zero_collection tests.test_collection_parity`
    — 7 tests, OK: the new file collects and both backends agree on its count.
  - `bash tests/run_all_python_tests.sh --test-dir tests` —
    `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, 3151 passed, 1 skipped.
