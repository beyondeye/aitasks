---
Task: t1674_nested_repo_boundary_regression.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1674 — Pin the nested-repository boundary of `_ait_detect_data_worktree()`

## Context

`_ait_detect_data_worktree()` (`.aitask-scripts/lib/task_utils.sh:68`) resolves
where task data lives through a four-rung ladder added by t1658_2. Rungs 2 and 3
derive an absolute `<root>/.aitask-data` from `git rev-parse --show-toplevel` and
from `ait_main_worktree_root()` respectively, and **both stop at a repository
boundary** — so a submodule, or any nested checkout, resolves to its *own* root
and therefore to legacy mode (`"."`), never to the parent repo's data branch.

Today that boundary is held by a **source comment only** (`# BOUNDARY:` at
`task_utils.sh:64-67`). Test 13 covers the cwd shapes and Test 14 covers the
indeterminate-topology refusal, but **no test exercises a nested repository**. A
later change to rung 2 or rung 3 could therefore make a nested checkout silently
operate on its parent's data branch — the same silent-wrong-target class t1658_2
exists to remove.

This task adds a regression test. It does **not** change the behaviour of
`_ait_detect_data_worktree()` — the boundary is already correct by construction.

### Behaviour confirmed empirically (scratch fixture, before planning)

| probe cwd | answer |
|---|---|
| branch-mode parent root | `.aitask-data` |
| plain nested repo inside it | `.` |
| real submodule inside it | `.` |

With rung 2 relaxed to walk up past repository boundaries (patched copy of
`task_utils.sh` in a scratch tree), both nested shapes answered
`<parent>/.aitask-data` instead of `.`. That establishes the shape is
discriminating; the post-phase below turns it into a demonstration against the
**committed** test, and extends it to rung 3, which the rung-2 experiment never
reaches.

---

### Pre-phase (risk mitigations)

**`assert_fixture_preconditions`** — before any boundary assertion runs, assert
that the fixture really built what the test claims to probe:

- the parent really is branch mode (`$ROOT_15/.aitask-data/.git` exists);
- each nested checkout really is its own repository (its
  `rev-parse --show-toplevel`, canonicalized, is itself);
- each nested checkout really is **inside** the parent's working tree — this is
  what makes the repository boundary the only reason for a `.` answer;
- neither nested checkout has a `.aitask-data` of its own;
- the submodule fixture really was created (its `.git` file is present).

These are hard assertions, never skips. An environment that blocks
file-transport submodule clones must fail *at the fixture*, with a message
naming the fixture — not at the boundary assertion, and never vacuously green.

---

## Approach

Add **Test 15** to `tests/test_task_git.sh`, inserted after Test 14 and before
the `--- Summary ---` block. It follows the file's existing style exactly: test
bodies at top level (no `( … )` subshells, so the in-process `PASS`/`FAIL`
counters keep working — no file-backed-counter opt-in needed), a cold-cache
`pushd`/`popd` probe helper, and `assert_eq_trim`.

### Fixture

One `setup_repo_with_remote` parent built into **branch mode** the way Test 13
does it (`SCRIPT_DIR="$ROOT_15/.aitask-scripts"`, `mkdir -p`, then
`(cd "$ROOT_15" && setup_data_branch </dev/null >/dev/null 2>&1)` —
`setup_data_branch` reads `$SCRIPT_DIR/..` as its project dir), containing:

- `vendor/` — a plain subdirectory of the parent (**no** repository boundary).
- `vendor/inner/` — **(A)** a plain nested checkout: `git init` + one commit, no
  `.aitask-data` of its own.
- `vendor/dep/` — **(B)** a real submodule, added from the fixture's own local
  bare remote so there is **no network round-trip**:
  ```bash
  git -c protocol.file.allow=always -C "$ROOT_15" \
      submodule add --quiet "$TMPDIR_15/remote.git" vendor/dep
  ```
  The `-c protocol.file.allow=always` is required on git ≥ 2.38, whose default
  `user` policy blocks file-transport submodule clones; older gits ignore the
  unknown key. Verified working in a scratch fixture.

### Assertions

Preconditions are the pre-phase block above.

**Positive control in the same fixture** — `detect_from "$ROOT_15"` is
`.aitask-data`. Without it, `.` from inside the nested repos could just mean the
fixture never got a data worktree.

**Adjacent control, the strongest discriminator** —
`detect_from "$ROOT_15/vendor"` is `$ROOT_15/.aitask-data` (rung 2). `vendor/` is
the *immediate parent directory* of both nested checkouts, so the only thing that
differs between it and them is the repository boundary — not depth, not the
fixture.

**The boundary contract**, for (A), for a subdirectory of (A), and for (B):

1. the answer is `.`;
2. the answer, resolved physically from the probe cwd, does **not** name the
   parent's data worktree (`(cd "$probe_cwd/$answer" && pwd -P)` vs
   `(cd "$ROOT_15/.aitask-data" && pwd -P)` → `differs`). This second half is
   what makes it a boundary test rather than a restatement of (1);
3. that same physical resolution **is** the nested checkout's own root.

Then `unset -f` the probe helpers and `rm -rf "$TMPDIR_15"`, matching Tests 13
and 14.

## Files changed

Two files, and the second is comment-only:

- **`tests/test_task_git.sh`** — the substantive change. New Test 15 block
  between Test 14's `rm -rf "$TMPDIR_14"` and `# --- Summary ---`.
- **`.aitask-scripts/lib/task_utils.sh`** — a **comment-only** edit inside the
  existing `# BOUNDARY:` block (lines 64-67), adding a pointer to Test 15. No
  code inside `_ait_detect_data_worktree()` changes; the task's "do not change
  the function" constraint is about behaviour, and the whole point of this task
  is that the boundary was held by that comment alone — naming its test is what
  closes the loop. This is deliberate and in scope.

---

### Post-phase (risk mitigations)

**`falsify_against_relaxed_ladder`** — the single owner of the falsifiability
argument (`## Verification` only points here). Run against the **committed**
test, not a scratch probe, and against **both** load-bearing rungs, because the
task's contract names rung 2 *and* rung 3 and a rung-2 mutation short-circuits
before rung 3 ever executes.

Setup, once: copy `.aitask-scripts/` into the scratchpad; run
`tests/test_task_git.sh` with `PROJECT_DIR` pointed at the copy.

**Mutation 1 — rung 2.** In the copy's `task_utils.sh`, replace rung 2's
`git rev-parse --show-toplevel` with a loop that walks up from `$PWD` past
repository boundaries looking for `.aitask-data/.git`. Expected: rung 2 itself
answers `<parent>/.aitask-data` for both nested shapes.

**Mutation 2 — rung 3.** Revert mutation 1, then relax **only**
`ait_main_worktree_root()` in the copy's `.aitask-scripts/lib/data_symlinks.sh`:
after it resolves normally, walk up from `AIT_WT_MAIN_ROOT` past repository
boundaries and, if an enclosing `.aitask-data/.git` is found, set
`AIT_WT_MAIN_ROOT` to that enclosing root. Rung 2 is left correct, so it still
misses for a nested checkout (inner has no `.aitask-data` of its own) and
execution genuinely reaches rung 3, which then answers `<parent>/.aitask-data`.

**Required outcome, recorded per mutation:** under each mutation independently,
the Test 15 boundary assertions (1), (2) and (3) **fail** for both nested shapes,
while the positive control (`$ROOT_15` → `.aitask-data`) and the adjacent control
(`$ROOT_15/vendor` → `$ROOT_15/.aitask-data`) stay green — that pairing is what
shows the failure comes from the boundary rather than from a broken fixture.
Record which assertions failed for each mutation in the Final Implementation
Notes.

A test that cannot fail adds nothing. The relaxed ladders live only in the
scratchpad; nothing in the repo is mutated.

---

## Verification

```bash
bash tests/test_task_git.sh          # must end "ALL TESTS PASSED"
shellcheck tests/test_task_git.sh    # no NEW findings vs. the baseline
```

Baseline note: `shellcheck tests/test_task_git.sh` already exits 1 on this file
(pre-existing `SC1091` infos on the three `source` lines and one `SC2034` at line
162). The bar is **no new findings**, compared against the baseline captured
before the edit — not a clean exit.

Plus the two-mutation falsifiability demonstration owned by the post-phase block
above.

## Step 9 (Post-Implementation)

Standard: commit as `test: <description> (t1674)`, then the Step 9 archival /
merge flow.

## Risk

*Reassessed once after both inline mitigations were confirmed (per
`risk-evaluation.md` Step 3's reassessment note). The augmented plan adds only
assertions and a verification pass — both levels stay `low`.*

### Code-health risk: low

- Blast radius is one new top-level block in `tests/test_task_git.sh` plus a
  comment-only line in `task_utils.sh`; no executable production code is
  touched. · severity: low · → mitigation: none needed
- The submodule half depends on `protocol.file.allow=always` and on
  `git submodule add` succeeding locally; an environment that blocks it would
  produce a fixture failure that reads as a boundary failure. · severity: low ·
  → mitigation: inline pre-phase assert_fixture_preconditions

### Goal-achievement risk: low

- The risk that the test is green-but-blind — that it would pass even if the
  boundary were removed from **either** rung 2 or rung 3. A rung-2-only
  demonstration is insufficient: it short-circuits before rung 3 runs, so a
  future rung-3 regression would be undemonstrated. · severity: low ·
  → mitigation: inline post-phase falsify_against_relaxed_ladder
- The task's second requirement ("the resolved value does not name the parent's
  data worktree") is covered explicitly by assertion (2), and the `vendor/`
  adjacent control pins that the difference is the repository boundary rather
  than the depth. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: assert_fixture_preconditions | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — submodule fixture depends on protocol.file.allow and could fail as a boundary failure | desc: Assert the parent is branch mode, each nested checkout is its own repo inside the parent tree with no .aitask-data of its own, and the submodule .git file exists.
- timing: post-phase | name: falsify_against_relaxed_ladder | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the test could be green-but-blind for rung 2 or rung 3 | desc: Run the committed test against two independent scratch-only mutations — a boundary-walking rung 2, and a boundary-walking ait_main_worktree_root that leaves rung 2 correct so execution reaches rung 3 — and confirm Test 15's boundary assertions fail under each while both controls stay green.
