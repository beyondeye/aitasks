---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-08 12:46
updated_at: 2026-09-08 12:46
---

## Origin

Risk-mitigation ("after") follow-up for t1725_1, created at Step 8d after implementation landed.

## Risk addressed

Code-health / goal — `./ait git pull` leaves a wedge, and the argv parser it needs
also fixes the refused `-c … rebase --abort` recovery.

From t1725_1's `## Risk`:
> The deferred gateway/crew/sync paths still leave wedges after this lands, so the
> parent's "any framework-driven pull" wording is not yet fully met · severity: low

## Goal

t1725_1 made `_task_pull_rebase` clean up a conflicted rebase it started. The
`./ait git` gateway still does not: `ait:333-345` dispatches `ait git <args>` to
`task_git "$@"`, which runs `git pull --rebase` directly, so a conflict through the
supported gateway leaves `rebase-merge` behind exactly as before.

Three coupled defects, all fixed by the same parser:

1. **`ait:333-345` → `task_git` runs the gateway pull unguarded.** Route a top-level
   `pull` subcommand through the ownership-checked cleanup t1725_1 added
   (`_data_wedge_state` → conflict-shaped output → rebase state → `orig-head` ==
   pre-pull HEAD → `ait_rebase_abort_if_ours`), so the gateway satisfies the same
   invariant.

2. **Routing cannot key on `$1`.** Git accepts global options before the
   subcommand, so `git -c pull.rebase=false pull` and `git --no-pager pull --rebase`
   would bypass a `$1 == pull` test entirely. Add a single
   `ait_git_subcmd_index <argv…>` parser returning the 1-based index of the first
   non-option token (0 when there is none — the fail-closed answer). It must know
   the closed set of value-taking global options (`-C`, `-c`, `--git-dir`,
   `--work-tree`, `--namespace`, `--exec-path`, `--config-env`, `--attr-source`;
   the `--opt=value` spelling consumes nothing extra).

3. **`lib/task_utils.sh:253` / `:274` have the same defect today.**
   `_ait_git_subcmd_is_readonly` and `_ait_git_subcmd_is_recovery` both key on
   `${1:-}`, so **`./ait git -c core.pager=cat rebase --abort` — the recovery
   command `assert_data_worktree_clean`'s own die message advertises — is
   classified as neither recovery nor read-only and is refused by the guard.**
   Retrofit both onto the parser: `assert_data_worktree_clean` computes the index
   once and passes `"${@:idx}"`, leaving their signatures and their existing
   `tests/test_task_git.sh` Test 16 coverage unchanged.

### Also decide: repo-redirecting global options

`-C`, `--git-dir`, `--work-tree` and `--namespace` silently retarget the gateway
away from the data worktree — which defeats its purpose — and would decouple the
pull from the git-dir the ownership evidence is read through. Recommended: reject
them at the gateway with a message naming the option and pointing at plain `git`.
`-c name=value` carries no redirect and must be preserved.

### Bound to state, not to imply

The t1725_1 helper cleans up a **rebase** it started, not a merge. A merge-mode
gateway pull that conflicts leaves `MERGE_HEAD`; `ait_rebase_abort_if_ours` returns
`not_ours` for any non-rebase state, so it is reported as `data_midop` and never
wrongly aborted. Closing the merge case needs its own `ORIG_HEAD` ownership
evidence — either do it here deliberately or state it as an explicit bound.

## Key files

- `ait` (~333-345) — the `git)` dispatch arm
- `.aitask-scripts/lib/task_utils.sh` — `task_git`, `_ait_git_subcmd_is_readonly`
  (~253), `_ait_git_subcmd_is_recovery` (~274), `assert_data_worktree_clean`,
  and t1725_1's `ait_rebase_abort_if_ours` / `_data_wedge_state` / pull mutex
- `tests/test_task_git.sh` — Test 16 is the six-state guard matrix to preserve
- `tests/test_task_push.sh` — Tests 39-47 are the t1725_1 patterns to mirror

## Verification

- Parser index table: `pull`→1; `-c a=b pull`→3; `--no-pager pull`→2;
  `-C dir -c a=b rebase --abort`→5; `--exec-path=/x status`→2; `-c a=b`→0; empty→0.
- **The latent recovery bug, pinned as a regression:** with `rebase-merge` planted,
  `assert_data_worktree_clean -c core.pager=cat rebase --abort` must be **allowed**
  (it is refused today) while `-c core.pager=cat commit` must still be **refused** —
  the paired assertion, so widening the parser cannot quietly open the guard.
- End-to-end through the real dispatcher: `./ait git pull --rebase` under a forced
  conflict → non-zero exit, no `rebase-merge`, no leftover `aitask-pull.lock`, and a
  following `./ait git commit` succeeds. Assert `-c core.pager=cat pull --rebase`
  **against the bare-form result** rather than a hand-written expectation, so the
  two cannot drift.
- Merge-mode: `./ait git -c pull.rebase=false pull` under the same conflict →
  `MERGE_HEAD` left in place, reported as `data_midop`, and neither sentinel nor
  hint contains `rebase`. (Asserting only "MERGE_HEAD survived" is insufficient —
  the wrong design also left it in place and merely described it wrongly.)
- Re-run `tests/test_task_git.sh` Test 16 unchanged.
