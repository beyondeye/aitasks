---
Task: t2234_contribution_plan_externalize_noworktree_still_writes_output.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2234 — plan_externalize `--no-worktree` writes `Output branch: main` (contribution, issue #15)

## Context

Contribution issue beyondeye/aitasks#15 (reported against framework **0.32.0**):
under a current-branch profile (`create_worktree: false`, e.g. `fast`), Step 6
calls `aitask_plan_externalize.sh --no-worktree --profile <p>`, and the helper
writes `Output branch: main` into the plan header even when the work is on
another branch (`dev`). Step 9 and Re-entry Routing resolve the merge target
from that header only, so in-flight work gets pointed at production `main`.

**Finding: this was already fixed by t2124** (commit `6b3161606`, "Record the
checked-out branch in current-branch plan headers and the task branch under
--worktree"), which first shipped in **v0.40.0**. The repo is at 0.40.1. Outside
worktree mode the helper now records the checked-out branch (detected primary
only on a detached HEAD) in both `Base branch:` and `Output branch:`, on both
the fresh-header path (`build_header`) and the existing-frontmatter splice path
(`splice_header_branches`; `--no-worktree` sets `OUTPUT_INTENT`/`BASE_INTENT`),
and it deletes a stale `Worktree:` line:

- `.aitask-scripts/aitask_plan_externalize.sh:588-597` — `WORKTREE_MODE != true`
  → `BASE_BRANCH_OVERRIDE=${CURRENT_BRANCH:-$PRIMARY_BRANCH}`,
  `OUTPUT_BRANCH_OVERRIDE=$BASE_BRANCH_OVERRIDE`.
- `tests/test_plan_externalize.sh` Test 17 (C1, C11, …) pins this behaviour in
  real git sandboxes on a `dev` checkout.

The contributor's proposed approach ("set Output branch to the current branch")
is exactly what t2124 implemented, so no code change is needed.

## Evidence (closure evidence — recorded verbatim)

1. `bash tests/test_plan_externalize.sh` → `Results: 326 passed, 0 failed` (rc=0).
2. Independent repro of the reported scenario, with a **pre-fix control**
   (script from `6b3161606^`) against the real `fast.yaml` profile, on a `dev`
   checkout, both for a plan without frontmatter (fresh) and for a source that
   already carries a stale `Worktree:` / `Output branch: main` header:

   ```bash
   S=<scratch>/t2234; R=<repo root>; mkdir -p "$S"
   git show 6b3161606^:.aitask-scripts/aitask_plan_externalize.sh > "$S/prefix.sh"
   run() { # $1=script $2=label $3=source-text
     local d="$S/$2"; mkdir -p "$d/aitasks" "$d/aiplans" "$d/plans" "$d/home"
     printf -- '---\nstatus: Ready\n---\nbody\n' > "$d/aitasks/t999_x.md"
     G() { HOME="$d/home" GIT_CONFIG_NOSYSTEM=1 git -C "$d" "$@"; }
     G init -q -b main; G -c user.email=a@b -c user.name=a commit -q --allow-empty -m i; G checkout -q -b dev
     G update-ref refs/remotes/origin/main HEAD; G symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
     printf '%b' "$3" > "$d/plans/internal.md"
     ( cd "$d" && mkdir -p .aitask-scripts && cp -r "$R/.aitask-scripts/lib" .aitask-scripts/ \
       && cp "$1" .aitask-scripts/aitask_plan_externalize.sh \
       && AIT_PLAN_EXTERNALIZE_INTERNAL_DIR="$d/plans" bash .aitask-scripts/aitask_plan_externalize.sh 999 \
            --internal "$d/plans/internal.md" --force --no-worktree \
            --profile "$R/aitasks/metadata/profiles/fast.yaml" >/dev/null 2>"$d/err" ); echo "rc=$?"
     echo "[$2] $(grep -E '^(Branch|Base branch|Output branch|Worktree):' "$d/aiplans/p999_x.md" | tr '\n' ';')"
   }
   STALE='---\nTask: t999_x.md\nWorktree: aiwork/t999_x\nBase branch: main\nOutput branch: main\n---\n# plan\n'
   run "$R/.aitask-scripts/aitask_plan_externalize.sh" cur_fresh '# plan\n'
   run "$R/.aitask-scripts/aitask_plan_externalize.sh" cur_stale "$STALE"
   run "$S/prefix.sh" pre_fresh '# plan\n'
   run "$S/prefix.sh" pre_stale "$STALE"
   ```

   Output (all rc=0):

   ```
   [cur_fresh] Branch: dev;Base branch: dev;Output branch: dev;
   [cur_stale] Base branch: dev;Output branch: dev;Branch: dev;
   [pre_fresh] Branch: dev;Base branch: main;Output branch: main;
   [pre_stale] Base branch: main;Output branch: main;
   ```

   The pre-fix control reproduces the reported bug (`Output branch: main`); the
   current helper records `dev` on both paths and drops the stale `Worktree:`.

## Implementation steps

1. **No code change.** Do not modify `aitask_plan_externalize.sh` or its tests —
   the fix and its regression coverage already exist (t2124).
2. Record the resolution in this plan's Final Implementation Notes: "already
   fixed by t2124 (`6b3161606`, v0.40.0); verified on 0.40.1 with the repro above".
3. Step 8: nothing to commit apart from the plan file (no code diff).
4. **Step 9 (Post-Implementation):** archive the task. The linked issue
   (#15) gets the standard Step 9 issue-update handling, which asks first. The
   suggested comment: fixed in v0.40.0 by t2124 (`6b3161606`); upgrade with
   `ait upgrade`.

## Verification

- `bash tests/test_plan_externalize.sh` stays green (326/326) — already run.
- The repro above: `cur_*` rows show `dev`, `pre_*` rows show `main`.

## Risk

### Code-health risk: low
None identified. (No code is changed.)

### Goal-achievement risk: low
None identified. The reported scenario (fast profile, `--no-worktree`, non-primary
checkout, fresh and stale-frontmatter sources) is reproduced against a pre-fix
control and shown fixed on the current tree.

## Final Implementation Notes
- **Actual work done:** No code change. Verified that the reported bug (issue #15, framework 0.32.0) was already fixed by t2124 (commit `6b3161606`, first shipped in v0.40.0): outside worktree mode `aitask_plan_externalize.sh` records the checked-out branch in both `Base branch:` and `Output branch:` (detected primary only on a detached HEAD), on both the fresh-header and the existing-frontmatter splice paths, and drops a stale `Worktree:` line. Evidence: `tests/test_plan_externalize.sh` 326/326 green (Test 17 C1/C11 pin the scenario) plus the pre-fix-controlled repro recorded above (current → `dev`, `6b3161606^` → `main`).
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Closed as already-fixed rather than adding a duplicate test; Test 17 already covers the contributor's exact scenario (fast-style `--no-worktree` on a non-primary checkout, fresh and stale-frontmatter sources).
- **Upstream defects identified:** None
