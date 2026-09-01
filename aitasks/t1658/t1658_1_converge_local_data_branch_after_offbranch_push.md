---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, task_metadata, robustness]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1658
created_at: 2026-09-01 14:30
updated_at: 2026-09-01 14:57
---

## Context

Child 1 of t1658. Covers **AC1–AC4** of the parent. See the parent plan
`aiplans/p1658_data_branch_metadata_push_strands_local_branch.md` for the full
root-cause analysis, the measured seam comparison, and the recorded decisions.

Every completed pick fires two metadata updates through
`satisfaction-feedback.md` (`aitask_usage_update.sh`, then
`aitask_verified_update.sh`). Both route into
`commit_and_push_from_remote_clone()` in
`.aitask-scripts/lib/verified_update_lib.sh:109`, which builds the commit in a
throwaway `/tmp` clone of `origin/<data-branch>` and pushes `HEAD:<branch>`
straight to origin. **The local branch ref is never advanced.** The only
compensation, `sync_current_repo_from_remote()` -> `task_sync()`, is a bare
`git pull --rebase` that refuses outright (exit 128, *before* it fetches)
whenever the shared `.aitask-data` worktree has unstaged changes. The outcome is
then discarded (`return 0`, no `TASK_SYNC_*` inspection), and `task_sync()` has
no push side. The local data branch drifts behind origin, the next local commit
lands on the stale tip and creates real divergence, and every later
`task_push()` fails non-fast-forward.

## Decisions already taken (do not re-litigate)

- **Reconcile seam = `git fetch` + `git merge --ff-only`** (user-approved
  deviation from the parent's AC2, which enumerated `--autostash` and
  `auto_commit()`). Measured on git 2.55.0 with a remote commit touching
  `meta.json` and the local worktree dirty on `task.md`: `pull --rebase` exits
  128 in both the non-overlapping and overlapping cases, while `merge --ff-only`
  returns 0 and preserves the dirty file when the paths do not overlap, and
  fails closed ("Your local changes ... would be overwritten by merge ...
  Aborting") when they do.
- `--autostash` is **rejected**: it runs an internal `git stash` across the
  shared `.aitask-data` worktree, removing other live sessions' unstaged
  `aitasks/` / `aiplans/` edits for the rebase window, and a failed pop leaves
  conflict markers. `auto_commit()` is **rejected** for the mirror reason: it
  stages `aitasks/ aiplans/` wholesale and would land other sessions' in-flight
  edits under an `ait: Update usage count ...` message (the unscoped-sweep
  pattern t1599 exists to remove). **The replacement must never stash and never
  commit anything.**
- **Success means the local-ref invariant holds.** A blocked fast-forward or an
  already-diverged branch leaves the commit on origin but not locally, so the
  scripts gain a distinct partial outcome rather than a warning attached to a
  success.
- **The chain stops returning its value through stdout.** Verified: a global
  assigned inside `$( )` does not cross back (`FLAG=1; inner() { FLAG=0; echo
  80; }; v="$(inner)"` leaves `FLAG=1`). The interface becomes out-param globals
  plus an exit code.

## Key files to modify

- `.aitask-scripts/lib/task_utils.sh` — add `task_data_converge()` and its
  `TASK_CONVERGE_*` globals in a new section after the `task_push` block; add
  `ff_blocked` and `local_diverged` arms to `_task_push_reason_hint()`
  (currently at :557).
- `.aitask-scripts/lib/verified_update_lib.sh` — pre-converge in
  `commit_metadata_update()`; rename `sync_current_repo_from_remote()` to
  `converge_current_repo_with_remote()`; capture the pushed sha, converge, and
  verify the invariant in `commit_and_push_from_remote_clone()`; convert the
  chain to out-param globals.
- `.aitask-scripts/aitask_usage_update.sh` (`main()` at :236) and
  `.aitask-scripts/aitask_verified_update.sh` (`main()` around :270) — drop the
  command substitution, read the globals, emit the two outcomes, document both
  in `--help`.
- `.claude/skills/task-workflow/satisfaction-feedback.md` — the single Claude
  source; `aitask_skill_rerender.sh` regenerates the `default` / `fast` /
  `remote` variants for Claude, Codex and OpenCode alike, so there is **no**
  per-agent port task.
- `tests/test_task_push.sh`, `tests/test_verified_update.sh`,
  `tests/test_usage_update.sh`, new `tests/lib/metadata_update_fixture.sh`.

## Reference files for patterns

- `task_sync()` / `task_push()` in `.aitask-scripts/lib/task_utils.sh:298` and
  `:406` — the best-effort-but-never-silent contract to mirror (always return 0,
  outcome in globals, one `warn()` on stderr, silent on success).
- `_task_push_classify()` (:~530) — the single source of pattern truth for
  reason codes; do not duplicate its greps.
- `_task_sync_warn()` (:354) — the warning shape to mirror.
- `tests/test_task_push.sh` — already has `setup_remote_and_clone()`,
  `advance_remote()`, `setup_branch_mode()` and `reload_task_utils()`.
- `tests/test_verified_update.sh:83` `setup_remote_repo()` — the origin + seed +
  work fixture the metadata tests use.

## Implementation plan

Follow `aiplans/p1658/p1658_1_*.md`, which carries the full step-by-step
design including the state matrix, the out-param interface, the outcome table,
and the two inline risk-mitigation post-phases
(`branch_mode_metadata_fixture`, `converge_race_stress`).

## Verification

```bash
bash tests/test_task_push.sh
bash tests/test_verified_update.sh
bash tests/test_usage_update.sh
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/aitask_verified_update.sh \
           .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/lib/verified_update_lib.sh
```

Live check on this repo: run
`./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`,
confirm it prints `UPDATED:` and exits 0, then confirm
`./ait git rev-list --count HEAD..@{u}` is `0` and `./ait git log -1 --format=%s`
names the usage-count commit — i.e. the commit reached the **local** branch.

## Out of scope

The cwd / data-worktree-resolution hazard (parent AC5) belongs to **t1658_2**.
Do not change `_ait_detect_data_worktree()` here.
