---
priority: high
effort: medium
depends: [t1658_1]
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1658
implemented_with: claudecode/opus5
created_at: 2026-09-01 14:30
updated_at: 2026-09-01 17:57
---

## Context

Child 2 of t1658. Covers **AC5** of the parent — the latent cwd hazard in the
same seam. See the parent plan
`aiplans/p1658_data_branch_metadata_push_strands_local_branch.md`.

`_ait_detect_data_worktree()` (`.aitask-scripts/lib/task_utils.sh:35`) resolves
`.aitask-data` **relative to the caller's cwd** and falls back to legacy mode
`"."` when it is absent. The fallback is silent and, by design, indistinguishable
from a genuine legacy-mode project. Reproduced on this repo: run from `website/`
-> `task_sync` pulls **`main`**; run from a crew worktree -> pulls
**`crew-brainstorm-1017`**. Both report success while the data branch is never
reconciled. **None of the 15 scripts that perform data-branch git ops `cd` to
the repo root** (`aitask_archive`, `aitask_artifact`, `aitask_attach`,
`aitask_create`, `aitask_fold_mark`, `aitask_followup_backfill`,
`aitask_gate_record`, `aitask_gate`, `aitask_issue_import`, `aitask_lock`,
`aitask_pick_own`, `aitask_remote_drift_check`, `aitask_sync`, `aitask_update`,
`aitask_zip_old`). Task worktrees are safe (task-workflow Step 5 runs
`aitask_init_data.sh --link-worktree`); crew worktrees are **not** linked —
verified missing on both live crew worktrees.

Separately, `aitask_usage_update.sh` / `aitask_verified_update.sh` resolve
`aitasks/metadata/models_<agent>.json` and `./ait` relative to cwd, so from a
subdirectory they die on "Model config not found" before any resolution fix is
reached.

## Decision already taken (user-selected)

**Anchor detection *and* both entry scripts** — not a narrow guard, and not
detection alone. A silent fallback to legacy mode from inside a branch-mode
project must not remain possible for any of the 15 scripts.

## Key files to modify

- `.aitask-scripts/lib/task_utils.sh` — replace `_ait_detect_data_worktree()`'s
  single cwd-relative probe with a four-rung ladder; add `ait_cd_repo_root`;
  add `source "${SCRIPT_DIR}/lib/data_symlinks.sh"`.
- `tests/lib/test_scaffold.sh` — `setup_fake_aitask_repo()` must copy
  `data_symlinks.sh`, per the source-on-startup <-> test-scaffold rule in
  `aidocs/framework/shell_conventions.md`. **Same commit** — every scaffolded
  test that sources `task_utils.sh` breaks otherwise.
- `.aitask-scripts/aitask_usage_update.sh`, `.aitask-scripts/aitask_verified_update.sh`
  — call `ait_cd_repo_root "$SCRIPT_DIR"` once at the top.
- `tests/test_task_git.sh` — resolution-rung tests.
- `tests/test_usage_update.sh`, `tests/test_verified_update.sh` — real
  entry-point subprocess tests from a non-root cwd.

## Reference files for patterns

- `ait_main_worktree_root()` in `.aitask-scripts/lib/data_symlinks.sh:96` — the
  canonical, submodule- and separate-git-dir-aware main-worktree resolver. Sets
  `AIT_WT_MAIN_ROOT`. **Reuse it; do not reimplement `--git-common-dir`
  handling.**
- `ait` (repo root, line 9) — `cd "$AIT_DIR"` is the rule `ait_cd_repo_root`
  mirrors.
- `tests/test_task_git.sh:1-70` — has `setup_repo_with_remote()` and sources
  `aitask_setup.sh --source-only` for `setup_data_branch`, which builds a real
  `.aitask-data` worktree (used at its Test 5).
- Existing detection tests `tests/test_task_git.sh` Tests 1–3 pin rung 1 and the
  legacy answer; they must keep passing unchanged.
- `tests/lib/metadata_update_fixture.sh` :: `setup_branch_mode_metadata_repo` —
  landed by sibling **t1658_1**; reuse it for the entry-point tests rather than
  forking a second branch-mode fixture.

## Implementation plan

Follow `aiplans/p1658/p1658_2_*.md`, which carries the ladder definition, the
consumer-safety audit, the entry-script anchoring, and the inline
risk-mitigation pre-phase `characterize_data_worktree_seam` that must run
**before** the ladder is touched.

## Verification

```bash
bash tests/test_task_git.sh
bash tests/test_usage_update.sh
bash tests/test_verified_update.sh
bash tests/test_remote_drift_check.sh
bash tests/test_init_data.sh
bash tests/run_all_python_tests.sh
shellcheck .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/aitask_verified_update.sh
```

Live check on this repo: from `website/`, run
`../.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`
and confirm it prints `UPDATED:` and exits 0 (today it dies with "Model config
not found"), then confirm `./ait git rev-list --count HEAD..@{u}` is `0` from
the repo root.

## Out of scope

The converge seam itself (parent AC1–AC4) belongs to **t1658_1**. Do not change
`task_data_converge()` or `verified_update_lib.sh` here beyond what the entry
scripts' `cd` requires.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T14:57:30Z status=pass attempt=1 type=human
