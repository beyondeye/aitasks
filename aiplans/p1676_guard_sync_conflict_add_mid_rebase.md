---
Task: t1676_guard_sync_conflict_add_mid_rebase.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1676 — Guard the interactive conflict-resolution `git add` mid-rebase

## Context

`ait sync` resolves data-branch conflicts in two stages: an automatic
frontmatter merge (`try_auto_merge`), and — for whatever the driver could not
resolve — an interactive loop that opens each remaining file in `$EDITOR` and
stages it.

The interactive loop is broken (`.aitask-scripts/aitask_sync.sh:1072-1084`):

```bash
local all_resolved=true
echo "$remaining" | while IFS= read -r f; do
    ...
    if $editor "$(_resolve_conflict_path "$f")"; then
        task_git add "$f" 2>/dev/null || true
    else
        warn "Editor exited with error for $f"
        all_resolved=false
    fi
done
```

Two defects, one root cause each:

1. **Unauthorized verb.** `add` is on neither `_ait_git_subcmd_is_readonly`
   nor `_ait_git_subcmd_is_recovery` (`lib/task_utils.sh:193,215`), so
   `assert_data_worktree_clean` (`:231`) sees the `rebase-merge` sentinel and
   calls `die` — which is `exit 1`. `|| true` cannot catch an `exit`, and
   `2>/dev/null` discards the diagnostic entirely.
2. **Pipeline subshell.** `echo … | while` runs the loop in a subshell, so that
   `exit 1` ends the *loop* after the **first** file. The same subshell also
   discards `all_resolved=false`, so the `else` branch below has never been
   able to influence the `if [[ "$all_resolved" == true ]]` check that follows.

Observed symptom: the editor opens for one file, the loop stops, `all_resolved`
is still `true`, `_rebase_advance` fails on the still-unmerged remainder, and
the user is told "Rebase continue failed" with no reason ever printed.

The sibling auto-merge site at `:940` already gets this right and is the
template:

```bash
add_err="$(AIT_GIT_SKIP_STATE_CHECK=1 task_git add "$f" 2>&1)" || add_rc=$?
```

Intended outcome: every remaining conflicted file is offered and staged, a
failed stage is reported rather than downgraded to "resolved", and an editor
failure actually reaches the `all_resolved` check.

## Files

- `.aitask-scripts/aitask_sync.sh` — the interactive loop in `do_pull_rebase`.
- `tests/test_sync_branch_mode_automerge.sh` — regression tests; its header
  already documents the authorization / swallowed-failure class and it carries
  the `setup_branch_mode_repos` and `install_failing_add_shim` helpers.

## Implementation

### Pre-phase (risk mitigations)

- **`characterize_interactive_loop`** — Write the three new tests (step 1) and
  run the file against the **unfixed** `aitask_sync.sh` **before** editing it.
  All three MUST fail, and each must fail *for its own reason*: Test 6 by
  reporting only `Editing: aitasks/t2_body.md` with `t3_body.md` absent; Tests 7
  and 8 by reporting `Rebase continue failed` instead of `Not all conflicts
  resolved`. If any passes pre-fix, or fails for the wrong reason, the fixture
  is vacuous — fix it before touching `aitask_sync.sh`. Addresses the
  goal-achievement risk below.

### 1. Regression tests (`tests/test_sync_branch_mode_automerge.sh`)

Add a fixture helper and three tests, appended before the `# --- Summary ---`
block. Assertions are at top level (no `( … )` bodies), so the file's existing
in-process `PASS`/`FAIL` counters need no opt-in.

**Two shared assertions**, used by Tests 7 and 8 (both take a failure exit):

- *Non-zero sync status.* `do_pull_rebase` returning 1 reaches `exit 1` in
  `main()` (`:1261`) and `ait` dispatches with `exec` (`ait:236`), so
  `./ait sync` must exit non-zero. Capture it explicitly
  (`rc=0; … ./ait sync … || rc=$?`) — a bare `|| true` would discard exactly
  the status being pinned.
- *No wedged worktree.* Resolve the data worktree's git-dir portably rather
  than hardcoding `.git/worktrees/-aitask-data/`:
  `gd=$(git -C "$TMP/local/.aitask-data" rev-parse --absolute-git-dir)`; assert
  neither `$gd/rebase-merge` nor `$gd/rebase-apply` exists, and that
  `git -C .aitask-data diff --name-only --diff-filter=U` is empty. Both failure
  branches call `task_git rebase --abort` (on `_ait_git_subcmd_is_recovery`, so
  it passes the guard) — this pins that the abort actually landed.

**Fixture — `setup_two_body_conflicts`.** Wraps `setup_branch_mode_repos` and
reshapes it so that **exactly one** local commit conflicts with **exactly one**
remote commit over **two** files, keeping the whole conflict in a single rebase
step (a multi-step rebase would need a second `_rebase_advance` round and make
the "did the rebase complete" assertion ambiguous):

1. In `local`: `git -C .aitask-data fetch -q origin` then
   `reset -q --hard origin/aitask-data` — discards the fixture's `local: labels`
   commit so `t1_sample.md` no longer participates.
2. In `local`: write `aitasks/t2_body.md` and `aitasks/t3_body.md` with
   `BODY FROM LOCAL`, one commit, **no push**.
3. In `pc2`: `git pull -q`, write the same two paths with `BODY FROM PC2`, one
   commit, push.

Body divergence (not frontmatter) is what makes the merge driver return
`PARTIAL`, so both files survive `try_auto_merge` into `remaining` — the same
mechanism Test 5 already relies on for its single file.

**Resolver editor.** A script in a scratch bindir that strips conflict markers
in place (awk: drop `<<<<<<< `, the `=======`→`>>>>>>> ` section, and the
`>>>>>>> ` line), so `$editor` genuinely resolves the file and returns 0. Path
must contain no spaces — `$editor` is expanded unquoted at the call site.

**Test 6 — both files are offered and both are staged.**

- Positive control first: fetch + rebase manually and assert
  `git diff --name-only --diff-filter=U` names **both** `t2_body.md` and
  `t3_body.md`; then `rebase --abort`. Without this the test could pass on a
  fixture that only ever produced one conflict.
- Run `EDITOR=<resolver> ./ait sync` (interactive, no `--batch`).
- Assert `Editing: aitasks/t2_body.md` **and** `Editing: aitasks/t3_body.md`
  both appear (strip ANSI with the file's existing `strip_ansi`). This is the
  assertion the pre-fix subshell exit fails.
- Assert the rebase concluded: no `rebase-merge`/`rebase-apply` under
  `.git/worktrees/-aitask-data/`, and `diff --name-only --diff-filter=U` is
  empty.
- Assert neither file still contains `<<<<<<<`.

**Test 7 — a failed stage is reported, not swallowed, and leaves no wedge.**

- Same fixture plus `install_failing_add_shim`, which fails `git add` only while
  a rebase is in progress in the data worktree.
- Run `EDITOR=<resolver> ./ait sync 2>err.txt`, capturing `rc`.
- Assert stderr carries `could not stage` and git's own
  `simulated staging failure` — pre-fix, `2>/dev/null` discards both and the
  `die` exits the subshell, so stderr says nothing about staging.
- Assert both files were still offered (the loop no longer dies on the first).
- Assert stderr contains `Not all conflicts resolved` and does **not** contain
  `Rebase continue failed` — pre-fix it is the other way round.
- Apply both shared assertions: `rc` non-zero, and no rebase sentinel / no
  unmerged path left behind.

**Test 8 — a failing editor reaches the `all_resolved` check.**

This is the branch Tests 6 and 7 do not touch: no `die` is involved, so the
*only* pre-fix defect is the `all_resolved=false` assignment dying with the
pipeline subshell. It is the behavior the task text calls out alongside the
staging bug.

- Same fixture, no shim, `EDITOR=false` (returns 1 for every file).
- Run `./ait sync 2>err.txt`, capturing `rc`.
- Assert stderr contains `Editor exited with error for aitasks/t2_body.md` and
  the same for `t3_body.md`. **Not a discriminator** — with no `die`, pre-fix
  code also offers both — but it pins that the loop still visits every file
  after the restructure.
- **The discriminator is the message pair:** assert stderr contains
  `Not all conflicts resolved` and does **not** contain `Rebase continue
  failed`. Pre-fix, the lost `all_resolved=false` sends control into
  `_rebase_advance`, which fails on the unstaged remainder and prints the
  latter.
- Apply both shared assertions. Note the non-zero `rc` is a **contract**
  assertion, not a discriminator: both branches `return 1`, so pre-fix exits
  non-zero too. It guards against a future regression that swallows the failure
  and reports `SYNCED`.

### 2. Fix the loop (`.aitask-scripts/aitask_sync.sh`)

Replace the `echo "$remaining" | while … done` body (currently `:1072-1084`)
with a herestring loop that mirrors `try_auto_merge`'s `done <<< "$conflicted"`
and its `:940` staging idiom:

```bash
                # `<<<`, NOT `echo | while`: a pipeline runs the loop in a
                # SUBSHELL, so `all_resolved=false` never reached the check
                # below, and a die() in the body killed only the subshell —
                # silently ending the loop after the FIRST file.
                local all_resolved=true
                while IFS= read -r f; do
                    [[ -z "$f" ]] && continue
                    echo ""
                    info "Editing: $f"
                    if $editor "$(_resolve_conflict_path "$f")"; then
                        # Staging a resolved conflict is exactly what this loop
                        # exists to do, and it owns the rebase it is resolving —
                        # so scope the documented bypass to this one call, as
                        # the auto-merge site above does. Without it
                        # assert_data_worktree_clean die()s mid-loop.
                        local add_err add_rc=0
                        add_err="$(AIT_GIT_SKIP_STATE_CHECK=1 task_git add "$f" 2>&1)" || add_rc=$?
                        if [[ $add_rc -ne 0 ]]; then
                            # A file we could not stage is NOT resolved:
                            # `rebase --continue` would fail later with the
                            # diagnostic already thrown away. warn() -> stderr.
                            warn "could not stage $f (git add rc=$add_rc): ${add_err:-<no output>}"
                            all_resolved=false
                        fi
                    else
                        warn "Editor exited with error for $f"
                        all_resolved=false
                    fi
                done <<< "$remaining"
```

Notes on the shape:

- The `add` stays inside `$( … )`. That is load-bearing now that the loop runs
  in the **current** shell under `set -euo pipefail`: any `die` reached through
  `task_git` is confined to the substitution and surfaces as a non-zero
  `add_rc`, instead of exiting `aitask_sync.sh` outright.
- `warn` (stderr), never `info`/`iinfo` — in interactive mode stdout is still
  the surface Test 5 pins as free of prose.
- The two neighbouring *display-only* `echo … | while` loops (`:1065`, `:1036`)
  are left alone: they only print and set nothing.

### Post-phase (risk mitigations)

- **`regress_sync_neighbours`** — After the fix, run the neighbouring sync
  suites (`tests/test_sync.sh`, `tests/test_sync_auto_commit_scoping.sh`,
  `tests/test_sync_deferral_and_quarantine.sh`, `tests/test_task_git.sh`) plus
  `shellcheck`. Addresses the code-health risk that moving the loop into the
  current shell changes `set -e` reach, and that `all_resolved=false` now
  actually routes to "Not all conflicts resolved. Aborting rebase."

## Verification

```bash
bash tests/test_sync_branch_mode_automerge.sh      # 5 existing + 3 new tests
shellcheck .aitask-scripts/aitask_sync.sh
bash tests/test_sync.sh
bash tests/test_sync_auto_commit_scoping.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_task_git.sh
```

Expected: all pass. The pre-phase additionally requires Tests 6, 7 and 8 to have
**failed** against the unfixed script, each for its own documented reason.

## Risk

### Code-health risk: low
- Moving the loop out of the pipeline subshell puts it in the current shell
  under `set -euo pipefail`, so a `die` reached from the body would now exit the
  whole script rather than just the loop · severity: low · → mitigation: inline
  post-phase regress_sync_neighbours (design keeps the `add` inside `$( … )`,
  which confines any `die` to the substitution)
- Making `all_resolved=false` effective makes the "Not all conflicts resolved.
  Aborting rebase." branch reachable for the first time — a behavior change on
  the editor-failure path, and the intended one · severity: low · → mitigation:
  inline pre-phase characterize_interactive_loop (Test 8 pins both directions of
  the message pair, so the branch flip is asserted rather than assumed)
- A second call site for the `AIT_GIT_SKIP_STATE_CHECK=1` bypass · severity: low
  · → mitigation: None (scoped to one call in the code path that owns the
  rebase — the documented use, identical to `:940`)

### Goal-achievement risk: medium
- The regression test only discriminates if the fixture actually delivers **two**
  files into `remaining` and reaches the interactive loop; a fixture that
  produces one conflict, or auto-merges both, would pass pre-fix and prove
  nothing · severity: medium · → mitigation: inline pre-phase
  characterize_interactive_loop
- The multi-round rebase path (`_rebase_advance` looping over several commits)
  could split the two conflicts across rounds, making "the rebase completed"
  ambiguous · severity: low · → mitigation: inline pre-phase
  characterize_interactive_loop (the fixture resets to `origin/aitask-data` so
  exactly one commit is replayed)
- A failure route could be "covered" only by a stderr substring while the run
  still reports success or strands the user mid-rebase — the two failure tests
  would then pass on a regression that wedges the worktree · severity: medium ·
  → mitigation: inline pre-phase characterize_interactive_loop (Tests 7 and 8
  both apply the shared non-zero-status and no-rebase-sentinel assertions)

### Planned mitigations
- timing: pre-phase | name: characterize_interactive_loop | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — tests may be vacuous; failure routes may be covered only by a message | desc: Write all three tests first and confirm each FAILS against the unfixed aitask_sync.sh for its own reason (Test 6 omits t3_body.md; Tests 7/8 print "Rebase continue failed" instead of "Not all conflicts resolved"), with Tests 7/8 also pinning a non-zero exit and a cleared rebase state
- timing: post-phase | name: regress_sync_neighbours | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — set -e reach and newly-reachable abort branch | desc: Run the neighbouring sync/task_git suites and shellcheck after the fix

## Step 9 (Post-Implementation)

Cleanup, archival of `t1676` + this plan, and merge follow the standard Step 9
of `task-workflow`. The task is a `followup_kind: upstream_defect` spawned from
t1599_3 under anchor 1599; the `risk_evaluated` gate is in its active set.
