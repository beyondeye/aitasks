---
Task: t2123_detect_primary_branch_short_ref_ambiguity.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2123 — detect_primary_branch: stop trusting `--short` abbreviation of origin/HEAD

## Context

`detect_primary_branch()` (`.aitask-scripts/lib/git_utils.sh:20`) and its Python
twin (`.aitask-scripts/lib/desync_state.py:67`) read
`git symbolic-ref --quiet --short refs/remotes/origin/HEAD` and strip `origin/`.
`--short` abbreviates *by ambiguity*: with a local branch literally named
`origin/main`, git answers `remotes/origin/main`, the strip misses, and
`remotes/origin/main` is returned as the primary branch (reproduced locally on
git 2.56). The value feeds plan headers (`aitask_plan_externalize.sh`),
`aitask_contribute.sh`, `aitask_note.sh` and the syncer's desync snapshot.
Upstream report from thinking_backend#t65 (another repository).

## Approach

Read the **full** target ref and accept it only when it is under
`refs/remotes/origin/`; otherwise fall through to the existing `main`/`master`
probe and `main` fallback. Resolution order is unchanged (t1031 maintainer
guard stays accurate).

Deliberate behaviour change (pinned by a test): an `origin/HEAD` that points
outside `refs/remotes/origin/` (hand-edited) no longer leaks its abbreviated
name; it falls through to the probes.

### 1. `.aitask-scripts/lib/git_utils.sh`

```bash
detect_primary_branch() {
    local head
    head="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null || true)"
    # Full ref, never --short: --short abbreviates by ambiguity, so a local
    # branch named "origin/main" turns it into "remotes/origin/main". (t2123)
    case "$head" in
        refs/remotes/origin/?*)
            printf '%s\n' "${head#refs/remotes/origin/}"
            return 0
            ;;
    esac
    ... (main/master probe + main fallback unchanged)
}
```
Update the header comment's step 1 to say "full target under refs/remotes/origin/".

### 2. `.aitask-scripts/lib/desync_state.py`

```python
proc = run_git(worktree, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
prefix = "refs/remotes/origin/"
if proc.returncode == 0:
    head = proc.stdout.strip()
    # Full ref, never --short (ambiguity abbreviation). (t2123)
    if head.startswith(prefix) and len(head) > len(prefix):
        return head[len(prefix):]
```
Probes/fallback unchanged; docstring tweak mirroring the bash comment.

### 3. Tests

`tests/test_git_utils.sh` (top-level asserts, no subshell-counter issue):
- **Test 5 (regression):** repo on `main`, `refs/remotes/origin/main` +
  `origin/HEAD -> refs/remotes/origin/main`, then `git branch origin/main`.
  Fixture precondition assert: `git symbolic-ref --short refs/remotes/origin/HEAD`
  == `remotes/origin/main` (proves the fixture actually triggers the ambiguity,
  so the test isn't vacuous). Then assert `detect_primary_branch` == `main`.
- **Test 6:** origin/HEAD → `refs/remotes/origin/trunk`, local branches `main`
  and `origin/trunk` → expects `trunk`. Only the symbolic-ref path can produce
  `trunk` (the probe would say `main`), so this proves the fix keeps that path
  live under the ambiguity instead of merely falling through.
- **Test 7 (outside-prefix, distinguishing setup):** repo with a local `main`
  branch and a local `trunk` branch; `git symbolic-ref refs/remotes/origin/HEAD
  refs/heads/trunk`. The unfixed code answers `trunk` (`--short` gives `trunk`,
  the `origin/` strip is a no-op); the fix falls through to the probe → `main`.
  Assert `main`. (A `refs/heads/main` target would be vacuous — old and new
  both answer `main` — so the target must differ from the probe's answer.)

`tests/test_desync_state.py`: new test in `DesyncStateTests` — direct call of
`desync_state.detect_primary_branch` on a fixture with origin/HEAD →
`refs/remotes/origin/trunk` and a local branch `origin/trunk` (precondition:
`--short` output is `remotes/origin/trunk`) → `trunk`; plus the outside-prefix
fallthrough case with the same distinguishing setup as bash Test 7 (local
`main` + `trunk`, origin/HEAD → `refs/heads/trunk`) → `main`.

Red proof: run every new bash and Python case against the unfixed functions
first — each of Tests 5, 6, 7 and both Python cases must FAIL there (Test 6
fails because old code returns `remotes/origin/trunk`; Test 7 because it
returns `trunk`), then pass against the fix. A case that passes on the unfixed
code is vacuous and gets redesigned.

## Out of scope

Other `symbolic-ref --short HEAD` sites (`aitask_merge_task.sh:84`,
`aitask_plan_externalize.sh:669`, `aitask_task_worktree.sh:392`,
`aitask_sync.sh:1954`, `task_utils.sh:820`, `shadow_scope.py:244`) are the
HEAD/tag-ambiguity class the downstream t65 handoff covers separately; the
task explicitly scopes that out. Mention as a possible follow-up at review.

## Verification

```bash
bash tests/test_git_utils.sh
bash tests/run_all_python_tests.sh --test-dir <scratch dir with test_desync_state.py>  # or python3 -m unittest tests.test_desync_state
bash tests/test_plan_externalize.sh; bash tests/test_contribute.sh; bash tests/test_note_append.sh   # callers
shellcheck .aitask-scripts/lib/git_utils.sh
```

## Step 9

Current-branch mode: commit code (`bug: ... (t2123)`) with explicit paths, plan via
`aitask_task_commit.sh`, then archive per Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `detect_primary_branch()` in `.aitask-scripts/lib/git_utils.sh` and its Python twin in `.aitask-scripts/lib/desync_state.py` now read `git symbolic-ref --quiet refs/remotes/origin/HEAD` (full ref) and accept it only when it starts with `refs/remotes/origin/` and names something after the prefix; anything else falls through to the unchanged `main`/`master` probe and `main` fallback. Added bash Tests 5–7 to `tests/test_git_utils.sh` (with a small `set_origin_head` fixture helper) and two cases to `tests/test_desync_state.py`. Every new case asserts its fixture precondition (`--short` output) so it cannot pass vacuously.
- **Deviations from plan:** None. The plan-review round replaced the outside-prefix fixture (`refs/heads/main`, vacuous because old and new code both answer `main`) with `refs/heads/trunk` beside a local `main`, which distinguishes them.
- **Issues encountered:** None. Red proof: all five new cases failed on the unfixed functions (`remotes/origin/main`, `remotes/origin/trunk`, `trunk` ×2 outside-prefix) and pass after the fix. Callers' suites green: `test_plan_externalize.sh` 264/264, `test_contribute.sh` 124/124, `test_note_append.sh` 124/124; `test_desync_state.py` + `test_desync_summary_cache.py` 22 passed; `shellcheck .aitask-scripts/lib/git_utils.sh` clean.
- **Key decisions:** Deliberate behaviour change — an `origin/HEAD` pointing outside `refs/remotes/origin/` is no longer trusted (it previously leaked its abbreviated name); pinned by bash Test 7 and the second Python case.
- **Upstream defects identified:** None
