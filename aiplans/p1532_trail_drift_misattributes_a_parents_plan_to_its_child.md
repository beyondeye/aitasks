---
Task: t1532_trail_drift_misattributes_a_parents_plan_to_its_child.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1532 — Trail drift misattributes a parent's plan to its child

Current-branch mode (profile `fast`, `create_worktree: false`) — no worktree, no
task branch.

## Context

`trail_gather.plan_glob_regex()` decides which stored `plan_file` input record
belongs to which trail member. For a **parent** id it builds

```
(?:.*/)?p<ID>_[^/]*\.md$
```

and applies it with `re.search`. The optional `(?:.*/)?` prefix happily consumes
`aiplans/p<ID>/`, so a parent's pattern **also matches its own children's plan
paths**:

```
plan_glob_regex("1159") matches BOTH
  aiplans/p1159_shadow_review_loop_automation.md   (correct)
  aiplans/p1159/p1159_4_docs_and_integration.md    (WRONG)
```

The child's own pattern is correctly scoped, so the fault is one-directional:
parent absorbs child, never the reverse.

The `drift` verb's per-member attribution picks the **first** matching stored
record via `next()` (`trail_gather.py:1061`). The gatherer emits `INPUT:` lines
sorted by ref, and `/` (0x2F) sorts before `_` (0x5F), so the **child's** plan is
emitted first — verified live:

```
INPUT:plan_file|true|3f6f24ae417fb673|aitasks:aiplans/p1159/p1159_4_docs_and_integration.md
INPUT:plan_file|true|e985fb391a82dbc6|aitasks:aiplans/p1159_shadow_review_loop_automation.md
```

The trail skill instructs the author to copy the INPUT lines' `(kind, ref)` pairs
into `generation.inputs` verbatim, so a faithfully-authored trail is reported
`STALE` with `plan_changed` by the same tool that produced it — and **no refresh
can clear it**, because every refresh reproduces the same ordering. The document
is not stale in any real sense; it is un-clearably mis-attributed.

The shape (a parent and one of its children both carrying plan files) was rare
when trails were built and is now common, since decomposing a member is the
normal way work proceeds.

**Outcome:** a parent's plan pattern stops matching its children's plan paths, so
per-member attribution is correct regardless of stored input order, and the
`art:trail-shadow-review-loop` ordering workaround becomes inert.

## Scope decision (confirmed with user)

Fix the code + tests only. The live `art:trail-shadow-review-loop` v5 workaround
(parent plan record emitted before the child's, documented as observation
`obs-plan-attribution-order`) is **left in place** — it stays valid after the fix
and its observation becomes a historical authoring note that the trail's next
`/aitask-trail refresh` will drop. Re-authoring a live trail belongs to that
flow, which owns the mandatory pre-write drift + schema validation.

## Approach

Suggested fix (1) from the task — *anchor the regex* — which the task records as
sufficient on its own and the smaller change. It is also the structural fix: it
makes the bad match impossible rather than making the consumer tolerate it, so
fix (2) (order-independent `next()` selection) is not needed and is not done.

Reviewing the anchoring surfaced a **second, adjacent defect in the same prefix**
(mid-segment matching, defect B below) that affects **both** branches of the
function and can likewise shadow a member's real plan record. It is the same
one-token prefix change, so it is fixed here rather than deferred — anchoring the
pattern while knowingly leaving the other hole in the anchor would be a
half-fix.

## Change 1 — `plan_glob_regex` (the fix)

`.aitask-scripts/lib/trail_gather.py:375-383` — the only change to shipped code.

Two independent defects in the same prefix, both fixed here:

- **A (the reported bug, parent branch only).** `(?:.*/)?` consumes the
  `p<ID>/` child-plan subdir, so a parent's pattern matches its own children's
  plans.
- **B (a boundary hole, both branches).** `(?:.*/)?` makes the directory prefix
  *optional* rather than requiring a path-segment boundary, and `re.search` may
  start anywhere. So `p<ID>` is matched mid-segment: `aiplans/notp1159_root.md`
  is attributed to member `1159`, and `aiplans/notp1159/p1159_4_x.md` to member
  `1159_4`. Because attribution takes the **first** match, such a stored ref —
  malformed, hand-authored, or from a project whose plan dir has similarly named
  siblings — can shadow the member's real plan record and mask a genuine
  `plan appeared` / `plan moved` condition. Requiring start-of-path or a slash
  closes it.

```python
def plan_glob_regex(own_id: str) -> re.Pattern:
    """Regex over a plan ref's *relpath* deciding whether it belongs to the
    member `own_id` (the identity-by-member rule for plan_changed)."""
    # `(?:^|.*/)`: `p<ID>` must start a path segment. The former `(?:.*/)?` made
    # the directory prefix optional, and `re.search` then matched mid-segment --
    # `aiplans/notp1159_root.md` was attributed to member 1159, shadowing its
    # real plan record (t1532).
    anchored = r"(?:^|.*/)"
    if "_" in own_id:
        parent, child = own_id.split("_", 1)
        pat = anchored + rf"p{parent}/p{parent}_{child}_[^/]*\.md"
    else:
        # `(?<!p<ID>/)`: a parent's plan lives DIRECTLY in the plan dir; the
        # `p<ID>/` subdir holds its children's plans. Without this guard the
        # prefix consumes `aiplans/p<ID>/` and the parent's pattern also matches
        # every child plan -- and because attribution takes the first match in
        # stored-input order, and the gatherer emits the child's ref first
        # ('/' < '_'), a faithfully-copied trail reported an un-clearable
        # `plan_changed` (t1532).
        pat = anchored + rf"(?<!p{own_id}/)p{own_id}_[^/]*\.md"
    return re.compile(pat + r"$")
```

Notes:

- The lookbehind is fixed-width for a given `own_id` (`len(own_id) + 2`), which
  is what Python's `re` requires.
- It deliberately omits the leading `/` so it also rejects a relpath with no
  directory prefix (`p1159/p1159_4_x.md`), where a `(?<!/p<ID>/)` form would
  have too few preceding characters and fail open.
- At position 0 (`p1159_x.md`, no directory at all) there is nothing to look
  behind, so the negative lookbehind succeeds and the parent still matches — the
  correct answer. `(?:^|.*/)` covers that case via its `^` alternative.
- Both guards are load-bearing: `(?:^|.*/)` alone still lets `.*/` swallow
  `aiplans/p1159/`, and the lookbehind alone still allows the mid-segment match.

Verified against the cases below — `old` is today's pattern, `A-only` is the
child-dir exclusion without the segment boundary, `new` is the code above:

| id | relpath | old | A-only | new |
|---|---|---|---|---|
| `1159` | `aiplans/p1159_shadow_review_loop_automation.md` | ✓ | ✓ | ✓ |
| `1159` | `aiplans/p1159/p1159_4_docs_and_integration.md` | ✓ | ✗ | ✗ |
| `1159` | `aiplans/notp1159_root.md` | ✓ | ✓ | ✗ |
| `1159` | `aiplans/xp1159/p1159_4_x.md` | ✓ | ✗ | ✗ |
| `1159` | `p1159_x.md` | ✓ | ✓ | ✓ |
| `1159` | `p1159/p1159_4_x.md` | ✓ | ✗ | ✗ |
| `1159` | `aiplans/archived/p1159_x.md` | ✓ | ✓ | ✓ |
| `1159` | `aiplans/archived/p1159/p1159_4_x.md` | ✓ | ✗ | ✗ |
| `1159` | `sub/aiplans/p1159_root.md` | ✓ | ✓ | ✓ |
| `115` | `aiplans/p1159_root.md` | ✗ | ✗ | ✗ |
| `1159` | `aiplans/p11591_x.md` | ✗ | ✗ | ✗ |
| `1159_4` | `aiplans/p1159/p1159_4_docs_and_integration.md` | ✓ | ✓ | ✓ |
| `1159_4` | `aiplans/p1159_shadow_review_loop_automation.md` | ✗ | ✗ | ✗ |
| `1159_4` | `aiplans/notp1159/p1159_4_x.md` | ✓ | ✓ | ✗ |
| `1159_4` | `p1159/p1159_4_x.md` | ✓ | ✓ | ✓ |

No other call site exists: `grep -rn plan_glob_regex` returns only the definition
(`:375`) and the single consumer in `cmd_drift` (`:1060`). No `aidocs/` or
website page describes the attribution rule, so there is no doc surface to
update — the docstring above is the documentation site.

## Change 2 — Guard tests

`tests/test_trail_gather.py`, section **E. Plan identity** (line 846), which
already owns the `plan_changed` / plan-attribution contract. Both guards the task
asks for, and the task is explicit that the unit test alone is insufficient — it
would pass a fix that only reordered the inputs.

### 2a. Unit test of the regex builder

New `PlanGlobRegexTests(unittest.TestCase)` placed immediately before
`PlanIdentityTests`. It needs no repo fixture, so it subclasses `unittest.TestCase`
directly rather than `TrailGatherCase`.

```python
class PlanGlobRegexTests(unittest.TestCase):
    """The identity-by-member rule itself (t1532). A parent's pattern must not
    absorb its children's plan paths, and neither pattern may match `p<ID>`
    mid-segment -- the old `(?:.*/)?` prefix did both."""

    def test_parent_pattern_rejects_child_plan_path(self):
        belongs = trail_gather.plan_glob_regex("1159")
        self.assertIsNone(
            belongs.search("aiplans/p1159/p1159_4_docs_and_integration.md"))
        self.assertIsNone(belongs.search("p1159/p1159_4_docs.md"))

    def test_parent_pattern_matches_its_own_plan(self):
        belongs = trail_gather.plan_glob_regex("1159")
        for path in ("aiplans/p1159_shadow_review_loop_automation.md",
                     "p1159_root.md", "sub/aiplans/p1159_root.md"):
            self.assertIsNotNone(belongs.search(path), path)

    def test_parent_pattern_is_id_exact(self):
        self.assertIsNone(
            trail_gather.plan_glob_regex("115").search("aiplans/p1159_root.md"))
        self.assertIsNone(
            trail_gather.plan_glob_regex("1159").search("aiplans/p11591_x.md"))

    def test_pattern_requires_a_path_segment_boundary(self):
        """`re.search` must not start mid-segment: a ref like
        `aiplans/notp1159_root.md` would otherwise be attributed to member 1159
        and shadow its real plan record."""
        self.assertIsNone(
            trail_gather.plan_glob_regex("1159").search(
                "aiplans/notp1159_root.md"))
        self.assertIsNone(
            trail_gather.plan_glob_regex("1159_4").search(
                "aiplans/notp1159/p1159_4_x.md"))

    def test_child_pattern_matches_only_its_own_plan(self):
        belongs = trail_gather.plan_glob_regex("1159_4")
        self.assertIsNotNone(
            belongs.search("aiplans/p1159/p1159_4_docs_and_integration.md"))
        self.assertIsNone(
            belongs.search("aiplans/p1159_shadow_review_loop_automation.md"))
```

### 2b. End-to-end `drift` test over a parent+child two-plan trail

Added to `PlanIdentityTests` (whose `setUp` already writes tasks `100` and
`100_1`). This is the guard that pins the user-visible behaviour.

A helper produces the same document with the `plan_file` records swapped **in
place** (task_file records keep their positions), so the only variable is plan
order:

```python
    def _swap_plan_inputs(self, trail: Path, trail_id: str) -> Path:
        """The same document with its plan_file records in the opposite order.
        Attribution must not depend on it (t1532)."""
        doc = json.loads(trail.read_text())
        inputs = doc["generation"]["inputs"]
        reversed_plans = iter(
            reversed([r for r in inputs if r["kind"] == "plan_file"]))
        doc["generation"]["inputs"] = [
            next(reversed_plans) if r["kind"] == "plan_file" else r
            for r in inputs]
        path = self.repo.root / f"{trail_id}.json"
        path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return path

    def test_parent_and_child_plans_current_in_both_input_orders(self):
        self.repo.write_plan("100", "root")
        self.repo.write_plan("100_1", "child")
        snap = self.snapshot("--scope", "task", "100")
        # The gatherer emits the child plan FIRST ('/' sorts before '_'); the
        # skill instructs the author to copy that order verbatim.
        plan_refs = [f[-1] for f in snap["inputs"] if f[0] == "plan_file"]
        self.assertTrue(plan_refs[0].endswith("p100/p100_1_child.md"),
                        plan_refs)
        gathered = self.make_trail(snap, entries=[
            ("mainproj#100", self.entry_snapshot(snap, "mainproj#100")),
            ("mainproj#100_1", self.entry_snapshot(snap, "mainproj#100_1")),
        ])
        swapped = self._swap_plan_inputs(gathered, "trail-plan-order-swapped")
        for label, trail in (("gathered order", gathered),
                             ("swapped order", swapped)):
            with self.subTest(order=label):
                result = self.drift(trail)
                self.assertEqual(result["verdict"], "CURRENT", result["raw"])
                self.assertEqual(result["reasons"], [], result["raw"])
        self.assertEqual(self.drift(gathered)["digest"],
                         self.drift(swapped)["digest"])
```

The `assertTrue(plan_refs[0]…)` line is not decoration: it pins the emitted
order the bug depends on, so the test cannot silently stop exercising the
regression if the gatherer's sort ever changes.

### Post-phase (risk mitigations)

Runs after Change 1 and Change 2 are in place, before the plan is considered
done. Both are inline mitigations confirmed during planning — no tasks are
created for them.

- **`pin_regex_boundary_edges`** — extend `PlanGlobRegexTests` past the primary
  parent-vs-child case so both guards' boundaries are pinned, not merely
  implied. Required assertions, each named in the test body:
  - directory-less relpath: `plan_glob_regex("1159")` must NOT match
    `p1159/p1159_4_docs.md` (the case a `(?<!/p<ID>/)` form would fail open on);
  - **path-segment boundary (defect B):** must NOT match
    `aiplans/notp1159_root.md`, and `plan_glob_regex("1159_4")` must NOT match
    `aiplans/notp1159/p1159_4_x.md` — the non-slash prefix case, covered by
    `test_pattern_requires_a_path_segment_boundary`;
  - archived nesting: must NOT match `aiplans/archived/p1159/p1159_4_x.md`, and
    MUST match `aiplans/archived/p1159_x.md`;
  - id-prefix exactness: `plan_glob_regex("115")` must NOT match
    `aiplans/p1159_root.md`, and `plan_glob_regex("1159")` must NOT match
    `aiplans/p11591_x.md`.

- **`verify_live_trail_reason_parity`** — after the fix, re-run `drift` over
  **both** live artifacts and diff the reason sets against the pre-fix baseline
  captured during planning (reproduced in Verification step 4). Assert: (a) no
  `plan_changed|aitasks#1159` reason appears in either input order, and (b) every
  pre-existing reason is still present and unchanged in wording, with any
  difference explainable as genuinely new drift (a task created or archived since
  the baseline). A reason that changed for any other cause is a regression and
  blocks the change.

## Verification

1. **Negative control (must fail before the fix).** Apply Change 2 only, run the
   module, and confirm these three **fail** by name:
   - `test_parent_and_child_plans_current_in_both_input_orders` (defect A, e2e),
     reporting `DRIFT:plan_changed|mainproj#100|plan moved: …`;
   - `test_parent_pattern_rejects_child_plan_path` (defect A, unit);
   - `test_pattern_requires_a_path_segment_boundary` (defect B, unit).

   Then apply Change 1 and confirm all three pass. A passing negative control
   means the guard is not guarding anything.

   ```bash
   bash tests/run_all_python_tests.sh --test-dir tests 2>&1 | tail -5   # or:
   python3 -m unittest tests.test_trail_gather -v
   ```

2. **Whole module, no regressions.** `PlanIdentityTests`, `DriftCodeTests`,
   `DeterminismTests` and the wrapper/handle integration tests all exercise
   `plan_changed`:

   ```bash
   python3 -m unittest tests.test_trail_gather -v
   ```

3. **Python suite** (read the LAST line for the verdict; the banner goes to
   stderr):

   ```bash
   set -o pipefail
   bash tests/run_all_python_tests.sh 2>&1 | tail -20
   ```

4. **Live acceptance against the real defect** — the shape the task documents,
   through the real CLI entry point. Pre-fix baseline captured during planning:

   ```
   art:trail-shadow-review-loop -> STALE, reasons: new_related_task ×3,
     other|-|content changed in one of: …, task_completed aitasks#1525
     DIGEST:4a0799bded85ffe6            (no plan_changed — workaround holding)
   art:trail-gates-framework-landing -> STALE, new_related_task ×2,
     task_completed aitasks#1263, DIGEST:117d8b14fe63cc8a
   ```

   After the fix, re-run both and confirm the reason sets are unchanged apart
   from genuinely new drift (tasks created/archived since), and that **no
   `plan_changed|aitasks#1159` reason appears**:

   ```bash
   for h in art:trail-gates-framework-landing art:trail-shadow-review-loop; do
     echo "=== $h"; ./.aitask-scripts/aitask_trail_gather.sh drift --trail "$h"
   done
   ```

5. **Real-world both-orders check.** Fetch the live shadow trail to a scratch
   file, build a copy with its two `plan_file` records swapped into the
   gatherer's own order (child first — the order the workaround avoids), and run
   `drift` on both. Before the fix the swapped copy emits
   `DRIFT:plan_changed|aitasks#1159|plan moved: …`; after the fix neither copy
   does, and both report the same `DIGEST:`. Scratch files go in the session
   scratchpad, never the repo.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`, `create_worktree: false`) — no worktree or
branch cleanup. Merge target is `main` (recorded in the header above). Then
`aitask_archive.sh 1532`; the `risk_evaluated` gate is the only active gate and
is recorded by the Step-9 orchestrator.

## Risk

### Code-health risk: low

- The two guards are subtler to read than the glob-ish prefix they replace, and
  either could be mis-adjusted later — re-adding a leading `/` to the lookbehind
  fails open for directory-less relpaths, and relaxing `(?:^|.*/)` back to
  `(?:.*/)?` silently reopens defect B. · severity: low · → mitigation: inline
  post-phase `pin_regex_boundary_edges`
- Drift *wording* changes for already-broken shapes. (a) A trail storing a
  child's plan record for a parent member that now has its own plan flips from
  `plan_changed: plan moved: <child> -> <parent>` to `plan_changed: plan
  appeared: <parent>`. (b) A stored ref matched only mid-segment (defect B) stops
  being attributed, so its member can newly report `plan appeared` instead of
  silently comparing against the wrong record. Both are `STALE`; no document can
  flip CURRENT → STALE, because every match either pattern loses is one it should
  never have had. · severity: low · → mitigation: inline post-phase
  `verify_live_trail_reason_parity`

### Goal-achievement risk: low

- None identified. The task specifies the defect, the fix, and the guard
  precisely; the fix is confined to one branch of one function with a single
  call site; and the acceptance is checked against the real artifact that
  exhibits the bug, not only against synthetic fixtures.

### Planned mitigations

- timing: post-phase | name: pin_regex_boundary_edges | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (lookbehind subtlety / fail-open on a future mis-edit) | desc: pin the lookbehind's boundary in PlanGlobRegexTests — directory-less relpath, archived nesting (both directions), and id-prefix exactness
- timing: post-phase | name: verify_live_trail_reason_parity | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (drift wording change for the already-broken shape) | desc: re-run drift over both live artifacts after the fix and diff reason sets against the pre-fix baseline; assert no plan_changed|aitasks#1159 and no unexplained reason change

Both dispositions are **inline** — they are executed as the `### Post-phase (risk
mitigations)` steps above and no tasks are created for them (Step 7 / Step 8d
read `before` / `after` lines only). Levels were reassessed against the augmented
plan and are unchanged (`low` / `low`): the phases add only test assertions and a
read-only re-run.
