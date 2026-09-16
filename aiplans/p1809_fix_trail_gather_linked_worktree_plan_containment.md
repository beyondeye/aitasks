---
Task: t1809_fix_trail_gather_linked_worktree_plan_containment.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1809 — Fix trail_gather plan containment in a linked worktree

## Context

`_contained_plan_path` (`.aitask-scripts/lib/trail_gather.py:1210`) confines
every plan ref to the **realpath of the project root**. That holds in the
primary checkout, where `aiplans/` is a symlink to `.aitask-data/aiplans`
*inside* the root. It breaks in a **linked worktree** (`aitask_init_data.sh
--link-worktree`), where `aiplans/` points into the *primary* checkout's
`.aitask-data`: every legitimate plan ref then realpaths outside the worktree
root, the caller (`trail_gather.py:1391`) stages `ref_outside_project:<ref>`,
and the whole drift run errors out.

Consequences today:
- `tests/test_roadmap_drift_contract.py` fails 2 tests in any linked worktree
  (`'ERROR:ref_outside_project:aitasks:aiplans/p1118/...' != 'STALE'`), while
  the same module passes in the primary checkout.
- `ait board` started from a linked worktree shows `(drift unavailable:
  ref_outside_project)` for a trail that is fine in the primary checkout.
- Worktree-mode profiles (`create_worktree: true`) link their worktrees exactly
  this way, so this hits real work, not only tests.

The same root-only rule breaks a second layout: a project whose `PLAN_DIR`
points **outside** its checkout. Refs are spelled with
`os.path.relpath(plan_path, tree.root)` (`trail_gather.py:437`), so such a plan
arrives as `../data/aiplans/p100_root.md` — upward segments that realpath out
of the root and are refused today. One fix covers both layouts.

Intended outcome: a plan ref that resolves into the project's **own** plan
directory is accepted wherever that directory physically lives, while every
other escape stays refused.

## Approach

Trust a **second containment base**: the realpath of the project's own plan
dir. That directory is project layout (`ProjectTree.plan_dir`, from
`_local_dirs()` / `root/"aiplans"`), never caller input, so trusting its target
widens nothing an untrusted ref controls — a ref that climbs out of the symlink
target still lands under neither base and is still refused.

### Step 1 — `.aitask-scripts/lib/trail_gather.py:1210`

Replace the single-base check in `_contained_plan_path` with a two-base one,
keeping the `ValueError` guard (different drives) and the `Path` return:

```python
root_real = os.path.realpath(tree.root)
target = os.path.realpath(os.path.join(root_real, relpath))
for base in (root_real, os.path.realpath(tree.root / tree.plan_dir)):
    try:
        if os.path.commonpath([base, target]) == base:
            return Path(target)
    except ValueError:
        continue
return None
```

`tree.root / tree.plan_dir` is correct for all three layouts: local
(`root=Path(".")`, `plan_dir=Path("aiplans")`), a `PLAN_DIR` override (absolute
values replace the join), and a sibling project (`root/"aiplans"`). Extend the
docstring with the linked-worktree reason and the traversal argument (t1809).

### Step 2 — `tests/test_trail_gather.py`, in `PlanIdentityTests`

Add next to the existing `test_traversal_ref_contained` (~line 1190), reusing
the existing `_trail_with_plan` helper:

0. Two fixture helpers gain an optional, **keyword-only** plan directory,
   defaulting to today's behavior so every existing caller is untouched:
   `SyntheticRepo.write_plan(..., *, plan_dir: Path | None = None)` (it
   currently hardcodes `self.root / "aiplans"` and ignores `PLAN_DIR`, so a
   symlink-less relocation would raise `FileNotFoundError` during setup), and
   `PlanIdentityTests._trail_with_plan(complete_snapshots, *, plan_dir=None)`,
   which forwards it. Create the target directory before writing.
1. A helper `_relocate_plan_dir(symlink: bool) -> Path` — `rename` the
   fixture's `aiplans/` to a directory **outside** `self.repo.root`, and when
   `symlink` is set, `symlink_to` it from the old location; returns the outside
   path. Both layouts under test differ only by that flag.
2. `test_symlinked_plan_dir_is_contained` — relocate with `symlink=True`, then
   build the trail via `self._trail_with_plan(True)`, which writes through the
   symlink exactly as a linked worktree does. Assert `errors == []` and verdict
   `CURRENT`. **This is the red test**: before Step 1 it fails with
   `ref_outside_project`.
3. `test_traversal_out_of_symlinked_plan_dir_still_refused` — NEGATIVE CONTROL
   for the widened base. With a `secret.md` written beside the relocated plan
   dir, a ref `mainproj:aiplans/../secret.md` must still produce
   `ref_outside_project` and no verdict. Without this, Step 1 could widen
   containment to the symlink's whole parent and the suite would stay green.

4. `test_absolute_plan_dir_outside_root_is_contained` — the second broken
   layout. Relocate with `symlink=False`, set `PLAN_DIR` to the returned
   absolute path (the base class already isolates and restores `PLAN_DIR`)
   **before** snapshotting, and build the trail with
   `self._trail_with_plan(True, plan_dir=outside)` so the plan is written into
   the external directory rather than the now-absent `root/aiplans`. The ref is
   then spelled with upward segments (`../data/aiplans/p100_root.md`). Assert
   `errors == []` and verdict `CURRENT`. Also red before Step 1, and it
   is what keeps a later refactor from satisfying the symlink case alone —
   e.g. by special-casing `Path.is_symlink()` rather than confining to the
   plan dir's realpath.

The existing `test_traversal_ref_contained` (`../../etc/passwd`) stays as the
root-relative control.

## Commit mechanics (do not use the Step 8 default)

Both files carry **another session's uncommitted hunks** (t1688 `task_declared`:
`trail_gather.py` ~lines 37/820/969, `test_trail_gather.py` lines 45 and 2713 —
all clear of my edits). `git commit -o -- <paths>` takes worktree content, so it
would commit their work under this task's `(t1809)` marker.

Instead: implement in the verification worktree (a clean `HEAD` checkout),
capture `git -C "$wt" diff > my.patch`, port it to the main tree, then commit
from a temporary index:

```bash
base=$(git rev-parse HEAD)
GIT_INDEX_FILE=$idx git read-tree "$base"
GIT_INDEX_FILE=$idx git apply --cached my.patch
tree=$(GIT_INDEX_FILE=$idx git write-tree)
new=$(git commit-tree "$tree" -p "$base" -F msgfile)
git update-ref refs/heads/main "$new" "$base"   # fails if main moved → rebuild on the new base
git reset -q -- .aitask-scripts/lib/trail_gather.py tests/test_trail_gather.py
```

`update-ref` with an expected old value makes this atomic against concurrent
sessions; `reset` realigns the real index so their hunks stay unstaged. Verified
preconditions: no commit hooks (`core.hooksPath` empty, no non-sample hooks), and
no staged content for either file.

## Verification

1. **Red proof** — add the tests from Step 2 first, before touching
   `trail_gather.py`:
   `python3 -m pytest tests/test_trail_gather.py -k "plan_dir or traversal"`
   → both containment tests (symlinked and absolute-`PLAN_DIR`) fail with
   `ref_outside_project`, both controls pass.
2. Apply Step 1; rerun the same selection → all pass. Then the whole module:
   `python3 -m pytest tests/test_trail_gather.py`.
3. **End-to-end in a real linked worktree** (the reported symptom, and the
   isolated-build check that proves my hunks stand alone without t1688's):
   ```bash
   git worktree add --detach "$wt" HEAD
   ./.aitask-scripts/aitask_init_data.sh --link-worktree "$wt"
   (cd "$wt" && python3 -m pytest tests/test_roadmap_drift_contract.py)  # control: 2 failures
   # apply my edits in $wt, then:
   (cd "$wt" && python3 -m pytest tests/test_roadmap_drift_contract.py tests/test_trail_gather.py)
   ```
   → the 2 drift-contract failures clear and `test_trail_gather.py` passes.
   Tear down with `git worktree remove "$wt"`.
4. Suite: `bash tests/run_all_python_tests.sh` — read only the last line
   (`PYTHON SUITE: …`); piping discards the status.

## Out of scope — recorded, not fixed here

The three zero-byte fixture-named files in the live tree (`aitasks/t1_alpha.md`,
`t2_beta.md`, `t10_gamma.md`) are **tracked on aitask-data**, swept in by
`2dabfae81` ("ait: Auto-commit task changes before sync", 2026-08-27);
`t1_alpha.md` was rewritten 2026-09-02, so the leak recurs. Which test leaks
them is unproven — `tests/test_data_branch_setup.sh:779` writes those exact
names but its Test 11 subshell looks isolated. Goes into the plan's "Upstream
defects identified" bullet so Step 8b offers it as a separate follow-up.

## Risk

### Code-health risk: low
- Widening the one untrusted-ref file-read sink from one containment base to
  two · severity: low · → mitigation: covered by Step 2's negative control
  (traversal out of the symlinked base must stay refused), the retained
  root-relative control, and the absolute-`PLAN_DIR` case that pins the rule as
  "confined to the plan dir's realpath" rather than "symlinks are special".
- Committing into two files that hold another session's in-flight hunks ·
  severity: low · → mitigation: covered by the temp-index commit mechanics and
  by verification 3, which runs my change alone on a clean `HEAD`.

### Goal-achievement risk: low
- The 2 drift-contract failures might not be caused by containment alone ·
  severity: low · → mitigation: covered by verification 3, which measures the
  real symptom in a real linked worktree against an unfixed control.

No `### Planned mitigations` subsection: every identified risk is already
mitigated by a core step of this plan, so there is nothing further to spawn or
inline.

## Post-implementation

Current-branch mode (profile `fast`): nothing is cut and nothing is merged, so
Step 9 skips the merge and runs `ait gates run 1809` (`risk_evaluated`) before
archival.

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan.
  `_contained_plan_path` (`.aitask-scripts/lib/trail_gather.py:1210`) now
  accepts a target under **either** the project root or the realpath of the
  project's own plan dir, iterating both bases and keeping the per-base
  `ValueError` guard. `tests/test_trail_gather.py` gained an optional
  keyword-only `plan_dir` on `SyntheticRepo.write_plan` and
  `PlanIdentityTests._trail_with_plan`, a `_relocate_plan_dir(symlink=…)`
  helper, and three tests: `test_symlinked_plan_dir_is_contained`,
  `test_absolute_plan_dir_outside_root_is_contained`, and the negative control
  `test_traversal_out_of_symlinked_plan_dir_still_refused`.

- **Deviations from plan:** The plan's temp-index commit mechanics
  (`read-tree` / `apply --cached` / `commit-tree` / `update-ref`) were designed
  around another session's uncommitted hunks in the same two files. That
  session committed its work mid-implementation as `8bb86c85c`
  (`enhancement: Read a no-plan in-flight task from its description
  (t1688_1)`), so those files then carried only this task's change and nothing
  was staged — the standard path-scoped `git commit -- <paths>` became both
  correct and simpler, and was used instead. The plumbing was never needed; the
  precondition it guarded against disappeared.

- **Issues encountered:**
  - `aitask_plan_externalize.sh` first answered `MULTIPLE_CANDIDATES` (four
    recent internal plan files); re-run with `--internal <path>` preserving
    `--force` and the branch flags.
  - `main` advanced during the session (`757a7e59f` → `002c74f45`), which is
    why the verification worktree was cut from the live HEAD rather than the
    branch tip recorded at session start.

- **Key decisions:**
  - Trust the **plan dir's realpath** as the second base rather than
    special-casing symlinks. `Path.is_symlink()` would have satisfied the
    linked-worktree case and still refused a `PLAN_DIR` pointing outside the
    checkout; the absolute-`PLAN_DIR` test exists specifically to pin that
    distinction.
  - The plan dir is project *layout*, never caller input, so the widening is
    not reachable by an untrusted ref — asserted by the negative control, which
    shows a ref climbing back out of the trusted target is still refused.
  - Implemented in an isolated linked worktree first, then ported by patch, so
    the change was proven to stand alone on a clean `HEAD`.

- **Upstream defects identified:**
  - `tests/test_data_branch_setup.sh:779-781 — zero-byte fixture task files
    (t1_alpha.md, t2_beta.md, t10_gamma.md) leak into the live aitasks/ tree
    and are tracked on the aitask-data branch (swept in by 2dabfae81,
    "ait: Auto-commit task changes before sync", 2026-08-27; t1_alpha.md
    rewritten 2026-09-02, so the leak recurs). These names are written by this
    test's Test 11 and by tests/test_boardcol_update.sh; which run actually
    leaks them is NOT proven — the Test 11 subshell appears isolated. They make
    every By-Trail discovery toast report "Trail scan skipped 4 unreadable
    active task file(s)". Deliberately out of scope here (scope confirmed with
    the user): fixing it means finding the leaking test, fixing its isolation,
    then deleting the files with a scoped aitask-data commit.`

- **Verification performed:**
  - Red proof: both containment tests failed with `ref_outside_project` before
    the fix; both traversal controls passed.
  - Linked worktree (`git worktree add --detach` + `aitask_init_data.sh
    --link-worktree`): `tests/test_roadmap_drift_contract.py` reproduced the
    reported 2 failures as a pre-fix control, then passed 3/3 after the fix.
  - Isolated worktree (clean HEAD + this change only):
    `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
  - Main tree: `tests/test_trail_gather.py` + `tests/test_roadmap_drift_contract.py`
    = 169 passed, confirming the change composes with t1688_1's landed work.
