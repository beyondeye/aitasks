---
priority: high
effort: high
depends: [t1912_3]
issue_type: refactor
status: Ready
labels: [git, concurrency, verifiedstats, models, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:42
updated_at: 2026-11-12 19:42
---

## Context

Child 4 of t1912. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. Depends on:
- t1912_1: store library + CLI `aitask_model_stats.py`;
- t1912_2: readers already read through the loader;
- t1912_3: task-data publication is re-homed to explicit pushes.

This is the cutover. The two counter writers stop touching `aitask-data`
entirely.

Today both writers source `lib/verified_update_lib.sh`:
- `.aitask-scripts/aitask_usage_update.sh`
- `.aitask-scripts/aitask_verified_update.sh`

The remote path is `commit_metadata_update` (~L275-323):
1. pre-converge (~L306);
2. clone origin, render, commit, push (`commit_and_push_from_remote_clone`
   ~L186-273);
3. post-converge (~L247).

The no-remote path is `commit_metadata_update_local` (~L147-184). The
counter render also runs through `ait_cas_rewrite` (`lib/registry_cas.sh`).

Exit/outputs today:
- `UPDATED:<agent>/<model>:<skill>:<value>` (exit 0);
- `UPDATED_REMOTE_ONLY:…` (exit 3).

## Goal

- Keep each writer's CLI exactly:
  - `--agent-string` | `--agent` + `--cli-id`;
  - `--skill`, `--date`, `--silent`;
  - `--score` (verified only);
  - the validation regex;
  - the model-exists check against the registry, now **read-only**;
  - the registration hint.
- Keep `UPDATED:<agent>/<model>:<skill>:<value>` with the same value
  semantics: usage → `month.runs`; verified → `round(all_time avg)`.
- Write through `aitask_model_stats.py bump-usage` / `record-verified`.
- Delete from the writers' path:
  - `commit_metadata_update*` and the clone path;
  - both converges;
  - the counter use of `ait_cas_rewrite` (`registry_cas.sh` stays for
    `aitask_opencode_models.sh` and the t1912_5 strip).
- Shrink or remove `verified_update_lib.sh`. Grep every sourcer first.
- **`verified` is no longer written** (user decision: it stays on
  `aitask-data` as a registry prior; readers derive the effective score).
- `UPDATED_REMOTE_ONLY` disappears for stats, as t1696 and the t1912
  "Related" section anticipated. A store failure prints `STATS_ERROR:` with a
  non-zero exit.

## Key files

- `.aitask-scripts/aitask_usage_update.sh`
- `.aitask-scripts/aitask_verified_update.sh`
- `.aitask-scripts/lib/verified_update_lib.sh`
- `.claude/skills/task-workflow/satisfaction-feedback.md`:
  - L31-32 and L103-104: remove `UPDATED_REMOTE_ONLY`;
  - add `STATS_ERROR` handling (warn and continue, never fail the
    workflow).
  - Then rerender, regenerate the goldens
    (`tests/golden/procs/task-workflow/satisfaction-feedback-*.md`) and run
    `./.aitask-scripts/aitask_skill_verify.sh`.
  - Suggest port tasks for `.agents/` / `.opencode/` if they are not
    rendered from the same source.
- Whitelist the new helper `aitask_model_stats.py` in the 5 touchpoints
  (`aidocs/framework/aitasks_extension_points.md` L367-415):
  - `.claude/settings.local.json`;
  - `.codex/rules/default.rules`;
  - `seed/claude_settings.local.json`;
  - `seed/codex_rules.default.rules`;
  - `seed/opencode_config.seed.json`.

  This applies only if a skill invokes it directly. If the writers stay the
  skill-facing entry points, it may need no entry; decide and state which.
  Run `tests/test_helper_whitelist_coverage.sh`.

## Tests to update / add

- **Acceptance (new):**
  - Setup: `.aitask-data` dirty (a modified tracked file plus an untracked
    file) and origin's `aitask-data` ahead.
  - A usage update and a verified update leave `.aitask-data` HEAD, the
    index (hash of `git ls-files -s`) and `git status --porcelain`
    byte-identical.
  - A `git` wrapper first on PATH logs argv. It must record no `fetch` /
    `merge` / `rebase` / `pull` / `push` involving `aitask-data`.
- `tests/test_usage_update.sh` and `tests/test_verified_update.sh`:
  - rollover tests via `--date` now read the store (CLI `show`/`export`, or
    `git cat-file`);
  - CAS-race tests against `models_*.json` go away for counters, with a
    stated reason;
  - remote tests move to the store.
- `tests/test_verified_update_flags.sh`
- `tests/test_metadata_partial_sync_recovery.sh`: it starts from a real
  stats `UPDATED_REMOTE_ONLY`, which can no longer happen. Retarget it to a
  different writer that still produces that partial outcome, or retire it
  with a stated reason.
- `tests/lib/metadata_update_fixture.sh`
- `tests/lib/test_scaffold.sh` (~L36)
- `tests/test_metadata_writer_inventory.py` L144-145: the writers no longer
  write `aitasks/metadata`. Remove the pins and keep discovery honest.
- `tests/test_skill_render_task_workflow.sh` ~L348-384
- `tests/test_task_data_writer_guard.sh` ~L270

## Verification

- All the above pass.
- `shellcheck .aitask-scripts/aitask_*.sh` is clean on the touched files.
- `bash tests/run_all_python_tests.sh` verdict line is PASSED.
- Manual smoke: run one usage update in this repo and confirm
  `git -C .aitask-data status` / HEAD are unchanged, and that
  `aitask_model_stats.py show` reflects the bump.

Step 9 (Post-Implementation) applies.
