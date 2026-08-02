---
Task: t1294_concern_body_display_contract_guard.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1294 — Guard the canonical-body vs display-body contract

## Context

t1274 split one piece of text into two readings and enforced the split only in
prose comments:

- `Concern.body` (`.aitask-scripts/monitor/concern_parser.py:174`) is
  **canonical** — exactly what the shadow emitted, terminal
  `Disposition: … Verified: …` trailer included. The forward path
  (`build_clipboard_payload`, `concern_parser.py:529`) re-renders it verbatim so
  the followed agent receives the metadata intact.
- `Concern.display_body()` (`concern_parser.py:184-192`) strips exactly that
  terminal trailer span. The row renderer (`_ConcernRow.render`,
  `monitor_shared.py:1293`) uses it so the picker shows prose, not metadata.

Both misuses are silent. `display_body()` on the forward path deletes the
disposition from what the agent receives; `.body` in a row puts metadata back
into the picker. Today nothing structural stops a *new* surface from reaching
for the wrong one.

**One premise in the task text has already resolved.** t1294 says to prefer an
approach that "keeps working when t1216_3 lands the full monitor's copy of the
picker". t1216_3 **has landed** (archived) — and it reused the shared
`ConcernPickerModal` / `_ConcernRow` rather than copying them. So the tree has
exactly **one** display surface and **one** forward surface, both serving both
monitors. That removes the "two divergent copies" scenario and shifts the real
residual risk to *a future third surface*, which is what this guard targets.

## What already exists (so this plan does not duplicate it)

Behavioural coverage of the two known surfaces is already in place:

- `tests/test_concern_picker_modal.py:416`
  `test_display_body_hides_the_trailer_from_the_row` — fails if `render()` is
  switched to `.body`.
- `tests/test_concern_parser.py:632`
  `test_body_stays_canonical_and_forwarding_is_byte_identical` — fails if
  `build_clipboard_payload` is switched to `display_body()`.

Being scope-honest about this: the **display** half of t1294's AC ("fails when
`_ConcernRow.render` is switched to `.body`") is *already* satisfied today by
the picker-modal test. This task's marginal value is therefore (a) the forward
half, (b) catching a **new** surface that neither behavioural test knows about,
(c) making the asymmetric rule explicit and role-annotated in one frozen table
instead of two prose comments, and (d) the negative controls the AC demands, at
a single named failure locus.

## Approach

One new self-contained `unittest` file,
`tests/test_concern_body_display_contract.py`, built on the repo's established
AST-guard precedent — `tests/test_board_persistence_seam.py:490-577` (frozen
registry + fail-closed scanner + variant negative controls) combined with the
in-memory mutation shape of `tests/test_board_fixture_harness.py`. There is no
written guard-test convention in `aidocs/framework/testing_conventions.md`; the
convention is precedent-only, so the plan names the precedent explicitly and the
implementation cites it in the module docstring.

### 1. Frozen accessor registry + scanner over the whole `monitor/` package

`_accessor_map(source: str, label: str) -> dict[(label, qualname, receiver), frozenset[str]]`
— AST-parse, build a parent map via `ast.iter_child_nodes`, and for every
`ast.Attribute` whose `attr` is `body` or `display_body`, resolve the enclosing
qualname and record `(label, qualname, receiver)` → the set of accessors used.
`_scan_package(dir)` is a thin wrapper that maps it over every `*.py` in the
package. Taking **source text, not a path** is what makes every negative control
a pure in-memory string mutation.

Five deliberate scanner decisions (the fifth, indexed reads, is detailed in
§2b):

- **Qualnames walk to the module root**, collecting every enclosing `ClassDef` /
  `FunctionDef` name and joining with `.`. Stopping at the first enclosing
  function (as the precedent does) would yield a bare `render` that collides
  across classes and loses the `_ConcernRow.` prefix that carries the meaning.
  Nested functions read `Outer.inner` — exactly the granularity wanted.

- **Receiver strings are built by hand**, not by `ast.unparse` — walk the
  `Name`/`Attribute` chain and join with `.`. Anything else (a call, subscript,
  literal, comprehension target) yields `"UNANALYSABLE: <reason>"`. This drops
  the `ast.unparse` dependency entirely, so the frozen registry cannot drift
  with a Python version bump.
- **`getattr(c, "body")` is covered too.** An `Attribute`-only scan is blind to
  it, which would be a silent hole in exactly the direction the guard exists to
  close. A matching `ast.Call` to `getattr` with a constant string in
  `{"body", "display_body"}` is recorded as an access; a non-constant second
  argument is recorded as `UNANALYSABLE`.
- **Constant-integer subscripts on Concern-linked names** are recorded as
  accessors named `"[<n>]"` — see §2b.
- **Fails closed** (the board precedent's `"UNANALYSABLE: …"` rule): every
  unresolvable case becomes a diagnostic string that can never compare equal to
  an expected entry — never silently dropped. An access outside any function
  gets qualname `<module>`, which is also a new key and therefore also trips.

Aggregating per `(label, qualname, receiver)` into a **set** is intentional:
occurrence counts are noise (an alias `b = c.body` inside a function must not
trip it), while a swapped accessor changes the set. Keeping the *receiver* in
the key is what makes each row self-classifying, and it catches a Concern read
newly added to a function that already reads an allowlisted receiver. Reads that
move to a helper, `row.concern.body`, or an unbound `Concern.display_body(c)`
all surface as new keys, i.e. fail closed.

**Scope is the whole `.aitask-scripts/monitor/` package**, not a hand-kept file
whitelist. `Concern` is a monitor-package type that is never exported, so the
package boundary is the true frontier; scanning it means a new Concern-body read
in *any* monitor file shows up as an unclassified key. A file whitelist, or a
whitelist of files importing `concern_parser`, would not: all three current
`concern_parser` importers read no body at all, so such a trigger does not
correlate with the risk. The cost of the wide net — unrelated `.body` reads — is
absorbed by the type-evidence pass below rather than by frozen per-site rows.
Scope stops at `monitor/` deliberately —
widening to all of `.aitask-scripts/` drags in unrelated `.body` on other types
(`applink/router.py:678`, `chatlink/wizard.py:328`) and buys nothing. This
rationale goes in the module docstring so nobody "improves" it later.

**The frozen table holds only Concern rows — unrelated reads are dropped by the
type-evidence pass (below), not frozen per-site.** (Revised after plan review:
an exhaustive table with `UNRELATED` rows keyed by `(file, qualname, receiver)`
churns on any unrelated `TaskDetailDialog` / `GateSummaryCache` edit — renaming
a method or adding a third `info.body` read — and, worse, trains reviewers to
mechanically stamp new rows `UNRELATED` without checking whether they are
actually Concern misuse. That dilutes exactly the review signal the guard
exists to produce.)

```python
FORWARD, DISPLAY, INTERNAL = "forward", "display", "internal"
_FORBIDDEN = {FORWARD: "display_body", DISPLAY: "body"}

# Source: .aitask-scripts/monitor/concern_parser.py:176-183 ("`body` is CANONICAL
#   … the clipboard path must always use `body`") and
#   .aitask-scripts/monitor/monitor_shared.py:1290-1292 ("display_body(), never .body").
# FROZEN, and every row is a Concern surface — there are no filler rows to
# rubber-stamp. A new or moved Concern-body read must consciously add one, WITH
# a role. A silent pass after a refactor is a bug in this table.
EXPECTED_ACCESSES = {
    ("concern_parser.py", "Concern.display_body",    "self"):          (INTERNAL, frozenset({"body"})),
    ("concern_parser.py", "build_clipboard_payload", "c"):             (FORWARD,  frozenset({"body"})),
    ("monitor_shared.py", "_ConcernRow.render",      "self._concern"): (DISPLAY,  frozenset({"display_body"})),
}

# Scoped exemptions for reads the evidence pass cannot classify. Keyed by
# (file, owning class/function, receiver) — never by receiver spelling alone,
# which is not a type identity. EMPTY today: every non-Concern read in the tree
# carries real annotations (see below), so nothing needs hand-exempting.
SCOPED_EXEMPTIONS: dict[tuple[str, str, str], str] = {}
```

**Unrelated reads are dropped by local type *evidence*, never by receiver
spelling.** (Revised after plan review — the previous draft's flat
`NON_CONCERN_RECEIVERS = {"info", "self._info"}` suppressed those spellings
across the whole package, so a Concern held in a variable named `info`, or any
other class using `self._info` for a Concern, would have had its `.body` read
silently dropped. A name is not a type.)

Per module, `_nonconcern_names()` resolves names **positively** bound to a
concrete non-`Concern` type, scoped to the function or class that binds them:

1. a parameter whose annotation **positively resolves** to a type in a small,
   explicit allowlist → non-Concern within that function;
2. `self.<attr> = <param>` in `__init__` where `<param>` so resolves →
   `self.<attr>` is non-Concern **within that class**;
3. `x = self.<attr>` where `self.<attr>` is already non-Concern → non-Concern
   within that function.

```python
# Concrete types whose instances are provably not Concerns. POSITIVE list: an
# annotation must resolve to one of these to exempt a read. Asserted never to
# contain "Concern".
NON_CONCERN_TYPES = {"TaskInfo"}   # monitor_core.TaskInfo — the task-record dataclass
```

**Resolution is closed-world, not "does not mention `Concern`".** (Revised after
plan review — a negative test is unsound: `Any`, `object`, a bare `TypeVar`, a
`Protocol`, or an unresolved alias can each carry a `Concern` without spelling
its name, silently exempting a `.body` read.) `_resolve_annotation()` accepts
only: a bare `Name`/`Attribute` whose final segment is in `NON_CONCERN_TYPES`;
`Optional[X]`; and `X | None` unions resolving to a single such type. It parses
string annotations before resolving. **Everything else returns `None` →
`UNCLASSIFIED`**, which is reported, not dropped.

Prototyped against the real tree and against the unsound cases:

| Annotation | Resolves to |
|---|---|
| `info: TaskInfo` (real, `monitor_shared.py:585`) | `TaskInfo` — exempt |
| `info: "TaskInfo \| None"` (real, `monitor_core.py:2793`) | `TaskInfo` — exempt |
| `Optional[TaskInfo]` | `TaskInfo` — exempt |
| `Any` / `object` / `T` / `SomeAlias` / `Renderable` | **UNCLASSIFIED** — reported |

Verified this covers all three unrelated reads in the real tree, with no
hand-written exemption:

- `monitor_shared.py:585` `TaskDetailDialog.__init__(self, info: TaskInfo)` →
  `self._info = info` (rule 1 → 2), covering the `:630` read;
- `monitor_shared.py:596` `info = self._info` in `_detail_widgets` (rule 3),
  covering the `:607` read;
- `monitor_core.py:2793` `GateSummaryCache.summary_for(self, info: "TaskInfo | None")`
  (rule 1), covering the `:2818` read.

Three properties keep this fail-closed rather than a hole:

- **Neither-classified is reported.** A read whose receiver resolves to *neither*
  Concern-linked (§2b) nor a concrete allowlisted type is emitted as
  `UNCLASSIFIED` and fails the equality assertion. Removing an annotation, or
  widening it to `Any`/`object`, removes the evidence and the read comes back
  into review — correctly. Exemption requires positive proof; absence of proof
  is never exemption.
- **Contradiction is an error.** A name resolving as *both* Concern-linked and
  non-Concern is reported, never silently resolved either way. This is what
  catches a Concern actually bound to a name like `info`.
- **`display_body` is never exempt.** It is defined on exactly one class in the
  whole repo (`concern_parser.py:184` — verified), so any `display_body` read is
  concern-bearing by construction and is reported regardless of receiver or
  evidence.

Churn is low without trading safety for it: adding another `info.body` read in
`TaskDetailDialog`, or renaming `_detail_widgets`, changes nothing — the
evidence still holds. Only removing the annotation, or introducing a genuinely
unclassifiable receiver, reaches review, and it arrives as a question.

(`Concern.display_body` reads `self.body` three times across `:191-192`; per-key
set aggregation collapses that to `{"body"}`, so occurrence counts — pure noise
— never trip the guard.) The source-trace comment above the table is required by
`aidocs/framework/code_conventions.md:9`, since the table condenses a contract
documented canonically at those two sites.

**Three assertions, three distinct jobs:**

1. `test_every_concern_body_read_in_the_monitor_package_is_declared` — exact map
   equality over the Concern-linked and unclassified reads. Catches drift and
   new surfaces. Its failure message prints four named buckets (undeclared
   reads / **unclassified** reads / vanished reads / **accessor set changed**),
   because a bare dict diff is unreadable in unittest output.
2. `test_no_surface_reads_the_accessor_its_role_forbids` — for each entry,
   assert the role's forbidden accessor is absent (`display_body` for `FORWARD`;
   `body` **and** `"[2]"` for `DISPLAY`). This is the assertion that **cannot be
   silenced by editing observed facts**: a maintainer who swaps `render()` to
   `.body` and "fixes" the red test by editing the expected set to `{"body"}`
   turns test 1 green but leaves test 2 red.
3. `test_evidence_classification_is_unambiguous` — pins the premises the
   evidence pass rests on: `Concern` is not in `NON_CONCERN_TYPES`; no name
   resolves as both Concern-linked and non-Concern; no evidence-backed receiver
   reads `display_body`; and `SCOPED_EXEMPTIONS` is still empty (a non-empty one
   must be justified in review, not accumulated silently).

A comment above the table states the corollary: if `render()` one day
legitimately needs `.body`, the fix is *not* to widen its set to
`{"body", "display_body"}` — it is to move that read into a separate helper
carrying its own `FORWARD`/`INTERNAL` role.

### 2. The one behavioural test the source scan structurally cannot replace

Every assertion in §1 compares *which accessor is called*. If `display_body()`
were reimplemented as `return self.body`, the map is unchanged
(`Concern.display_body` already maps to `{"body"}`), the whole source guard goes
green, and the picker silently shows trailers again. One cheap runtime test
closes that:

```python
def test_display_body_is_not_an_alias_of_body(self):
    """The precondition the whole source guard rests on."""
    c = Concern("high", "r", "Prose. Disposition: blocking. Verified: CONFIRMED.",
                "blocking", "CONFIRMED")
    self.assertIn("Disposition:", c.body)
    self.assertNotIn("Disposition:", c.display_body())
    self.assertNotEqual(c.display_body(), c.body)
```

The two *existing* behavioural tests are cross-referenced by full node id in the
module docstring, **not** duplicated — re-staging a Textual `Pilot` host here
would buy no new information and would drag `textual` into an otherwise
import-free, millisecond-fast guard. Only this one test needs `sys.path`; the
AST half imports nothing from the tree, so the guard still runs when `textual`
is unavailable.

### 2b. Indexed reads (`c[2]`) are checked, not merely disclaimed

`Concern` is a `NamedTuple`, so `c[2]` reads the canonical body and bypasses
`display_body()` entirely — a direct route for a future display surface to put
trailers back on screen. The behavioural test in §2 does **not** cover this: it
only proves today's `display_body()` is not an alias of `body`. So the guard
checks it rather than disclaiming it. (Revised after plan review.)

The scanner resolves, per module, a set of names it can **link to `Concern`**
— additive inference only, so imprecision costs recall, never false alarms:

1. parameters annotated `Concern`, and the `for X in <param>` loop targets of
   parameters annotated `list[Concern]` / `Sequence[Concern]` (this is what
   resolves `c` in `build_clipboard_payload`, whose signature is
   `concerns: list[Concern]` — verified present at `concern_parser.py:520`);
2. names bound from `Concern(...)` or `parse_concerns(...)`;
3. `self` inside the `Concern` class body;
4. receivers already carrying a role in `EXPECTED_ACCESSES` (e.g.
   `self._concern`).

Any `ast.Subscript` with a **constant integer index** on a linked name is
recorded as an access under the synthetic accessor name `"[<n>]"`. Index `2` is
`body`, so it lands in the same map, under the same roles, and trips the same
two assertions — a `DISPLAY`-role surface reading `c[2]` is forbidden exactly as
`.body` is. A **non-constant** index on a linked name records `UNANALYSABLE`.

The registry gains no rows today (there are no indexed reads in the tree), and a
fifth negative control proves the check discriminates:

| Control | Mutation (in memory) | Asserts |
|---|---|---|
| Indexed bypass | `monitor_shared.py`: `escape(self._concern.display_body())` → `escape(self._concern[2])` | `("monitor_shared.py", "_ConcernRow.render", "self._concern")` → `{"[2]"}`; role rule trips (a `DISPLAY` surface must read `display_body`) |

**Precisely-stated residual.** The guarantee is now: *every `body` /
`display_body` attribute read in the monitor package, plus every constant-index
tuple read through a name the scanner can link to `Concern` within its own
module.* Not covered: a Concern reaching an unannotated parameter in a module
that never names `Concern`, then indexed there. That is a real hole, it is
narrow, and it is stated as such in the module docstring — matching how the repo
documents scanner blind spots (`concern_parser.py:507-511`). The alternative,
flagging every integer subscript in the package, would drown the guard in
`lines[0]` / `args[1]` noise and is rejected.

### 3. Negative controls (the AC's "demonstrated, not assumed")

All controls go through one helper, which **asserts the anchor is unique**
before substituting — the precedent's `replace(old, new, 1)` would otherwise
silently hit the wrong site and a no-op mutation would masquerade as a pass:

```python
def _variant(self, path, old, new):
    src = path.read_text(encoding="utf-8")
    self.assertEqual(src.count(old), 1, f"anchor is not unique in {path.name}: {old!r}")
    return _accessor_map(src.replace(old, new, 1), path.name)
```

| Control | Mutation (in memory) | Asserts |
|---|---|---|
| **AC #1** — display surface switched to canonical | `monitor_shared.py`: `escape(self._concern.display_body())` → `escape(self._concern.body)` | `("monitor_shared.py", "_ConcernRow.render", "self._concern")` → `{"body"}`; map ≠ registry; role rule trips |
| **AC #2** — forward surface switched to display | `concern_parser.py`: `{c.body}` → `{c.display_body()}` in the f-string | `("concern_parser.py", "build_clipboard_payload", "c")` → `{"display_body"}`; map ≠ registry; role rule trips |
| New-surface catcher | `monitor_shared.py`: `return self._concern` → `return self._concern.body` (in the `concern` property) | a new unclassified key `("monitor_shared.py", "_ConcernRow.concern", "self._concern")` appears |
| Fail-closed (dynamic) | `monitor_shared.py`: → `escape(getattr(self._concern, which))` | an `UNANALYSABLE: …` entry is produced, never dropped |

Every control here is a pure in-memory string mutation — nothing is written to
disk, nothing needs restoring, and the production tree is never opened for
writing. The only disk-touching step in the whole task is the end-to-end
acceptance run (Verification 2), which works on a `tempfile.mkdtemp` copy of the
package, purges `__pycache__` in the copy (the repo's recurring pitfall when a
control copies a tree), asserts the real package is byte-identical afterwards,
and cleans up via `addCleanup`. Each control is preceded by its positive control
(the unmutated source matches the registry) so a failing control can never be
blamed on a broken fixture.

Naming and docstrings follow the in-tree convention
(`test_concern_picker_modal.py:401` — "Negative control: prove the assertion
above can fail … if this ever starts passing, the tests above have stopped
discriminating").

### 4. Bidirectional cross-reference

A guard is only useful if the person about to break it can find it. Repo
convention (and `code_conventions.md`'s source-trace rule read in the other
direction) wants a pointer at each guarded site:

- one-line comment at `concern_parser.py:528` and inside the existing
  `monitor_shared.py:1290-1292` comment block, naming
  `tests/test_concern_body_display_contract.py` as the table that freezes the
  rule;
- the new file's docstring points back at both sites, plus the two existing
  behavioural tests by full node id.

## Files

| File | Change |
|---|---|
| `tests/test_concern_body_display_contract.py` | **new** — role-annotated registry, type-evidence exemption pass, package scanner (attribute / `getattr` / indexed), 3 contract assertions, 1 behavioural test, 5 negative controls, 1 temp-copy end-to-end acceptance test |
| `.aitask-scripts/monitor/concern_parser.py` | +1 comment line at the `build_clipboard_payload` body access pointing at the guard |
| `.aitask-scripts/monitor/monitor_shared.py` | +1 comment line in the existing `render()` comment block pointing at the guard |

Standard test-file boilerplate per repo convention: `from __future__ import
annotations`; module docstring naming the task (`t1294`), the precedent being
followed (`tests/test_board_persistence_seam.py:490-577` — the convention is
precedent-only, there is no written guard-test rule in
`aidocs/framework/testing_conventions.md`), the two cross-referenced behavioural
tests by full node id, the `monitor/`-scope rationale, and the `c[2]` residual;
a `Run:` footer; per-file `sys.path` bootstrap from `__file__` (the runner
scrubs `PYTHONPATH` deliberately); `unittest.TestCase`; and
`if __name__ == "__main__": unittest.main()`.

Scanner detail worth pinning: a file in the package that fails to parse must
**raise**, never `except SyntaxError: continue` — a guard that skips what it
cannot read is a guard that passes on a broken tree.

## Adjacent staleness found during exploration (deliberately NOT fixed here)

Both were surfaced during exploration and both are out of t1294's scope. Asked
and answered at planning time: **leave them untouched**, record them in Final
Implementation Notes so they can be picked up separately.

- `monitor_shared.py:1336` — `ConcernPickerModal`'s docstring still says
  minimonitor is the only caller; t1216_3 made `monitor_app.py` a caller too.
- `.claude/skills/aitask-shadow/concern-format.md:227` — consumer list omits
  `monitor_app.py`.

## Verification

1. New guard passes on the current tree:
   `python3 -m unittest tests.test_concern_body_display_contract -v`
   — all tests pass, including the five controls.
1b. Confirm the evidence pass absorbs churn without hiding misuse: in in-memory
   variants, (i) rename `TaskDetailDialog._detail_widgets` → map **unchanged**;
   (ii) add a second `info.body` read in that class → map **unchanged**;
   (iii) drop the `info: TaskInfo` annotation → the read reappears as
   `UNCLASSIFIED`; (iv) **widen** it to `Any`, then to `object` → still
   `UNCLASSIFIED`, never exempt (the soundness control for the positive list);
   (v) rebind `self._info` from a `Concern(...)` call → contradiction reported.
2. **End-to-end AC demonstration — in a temp copy, never the working tree.**
   The plan-review point is well taken: editing `monitor_shared.py` in place on
   the shared current branch and relying on an exact manual undo risks leaving a
   stray edit in a dirty worktree if a run is interrupted or an anchor moved.
   Instead, since `_scan_package(dir)` is directory-scoped:

   ```
   copy .aitask-scripts/monitor/ → $TMP/monitor   (ignore __pycache__)
   record sha256 of every file in the real package
   for each of the three swaps — render→.body, payload→display_body(),
       render→self._concern[2] — mutate ONLY the temp copy, run the
       guard's assertions against _scan_package($TMP/monitor), require failure
   assert the real package's hashes are byte-identical afterwards
   rm -rf $TMP  (addCleanup, ignore_errors=True)
   ```

   This is a genuine end-to-end run of the real scanner over a real package
   directory, with the production tree provably untouched — no manual undo, no
   `git checkout`, nothing to leave behind.
2b. Confirm the guard is not vacuous in the other direction: it must run and
   pass with `textual` unimportable (the AST half imports nothing from the tree)
   — check by running only the source-scan test class.
3. No regression in the concern suites:
   `python3 -m unittest tests.test_concern_parser tests.test_concern_picker_modal
   tests.test_minimonitor_concern_action tests.test_monitor_concern_action -v`
4. The new file satisfies the meta-guards:
   `python3 -m unittest tests.test_no_zero_collection -v` and
   `bash tests/test_python_bootstrap_isolation.sh`
5. Full suite (last line is the verdict):
   `bash tests/run_all_python_tests.sh`

## Risk

### Code-health risk: low

- The guard scans the whole `monitor/` package, so it sits on code unrelated to
  concerns. Mitigated by deriving unrelated-read exemptions from **local type
  evidence** (annotations already present in the tree) rather than from a frozen
  per-site table or a receiver-spelling allowlist — either of which would trade
  review signal or safety for low churn. Renames and additional reads through an
  evidence-backed receiver cost nothing; the hand-written `SCOPED_EXEMPTIONS`
  list is empty and is asserted to stay that way · severity: low ·
  → mitigation: none needed
- The evidence pass is a small bespoke inference (three rules over a
  closed-world type allowlist) rather than a real type checker, so it will not
  resolve every future binding pattern. It is built to fail *toward* review —
  anything not positively resolved becomes `UNCLASSIFIED`, never silently
  dropped — so the failure mode is a question in review, not a missed misuse
  · severity: low · → mitigation: none needed
- No production behaviour changes at all (one new test file + two comment
  lines), so stability and blast radius are effectively nil · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low

- The source scan pins accessor **spelling**, not runtime behaviour; closed
  in-file by `test_display_body_is_not_an_alias_of_body` · severity: low ·
  → mitigation: none needed
- Indexed reads (`c[2]`) are checked (§2b), but only through names the scanner
  can link to `Concern` within their own module. A Concern reaching an
  unannotated parameter in a module that never names `Concern`, then indexed
  there, is not caught. Narrow, deliberate, and stated precisely in the module
  docstring rather than papered over · severity: low · → mitigation: none needed

## Step 9 (Post-Implementation)

Current-branch workflow — no worktree to remove. Merge approval, then
`./ait gates run 1294` (declares `risk_evaluated`), then
`./.aitask-scripts/aitask_archive.sh 1294`.
