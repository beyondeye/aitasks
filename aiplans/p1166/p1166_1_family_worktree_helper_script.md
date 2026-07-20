---
Task: t1166_1_family_worktree_helper_script.md
Parent Task: aitasks/t1166_shared_worktree_for_child_task_families.md
Sibling Tasks: aitasks/t1166/t1166_2_family_worktree_frontmatter_field.md, aitasks/t1166/t1166_3_task_workflow_family_mode_main_path.md, aitasks/t1166/t1166_4_family_failure_recovery_surfaces.md, aitasks/t1166/t1166_5_family_worktree_docs_and_profile_surface.md
Base branch: main
---

# Plan: t1166_1 — Family-worktree helper script + sync mechanics (spike-first)

## Context

The riskiest piece of t1166, isolated as a standalone, fully unit-testable helper with **no skill edits**. It owns all git mechanics for family worktrees: create/reuse, drift sync, path-level partial sync to main, rollback, final merge, teardown, and the hard concurrency guard. The parent plan (`aiplans/p1166_shared_worktree_for_child_task_families.md`) pins every verb contract — reproduce them exactly; downstream children (t1166_3/4) consume these contracts verbatim.

**Load-bearing design facts (do not re-derive):**
- Partial sync = **per-path checkout onto main + one plain commit**. Never `merge --no-commit` + restore: a partial merge commit advances `merge-base(main, aifamily/tN)` past the *ineligible* changes, so the final three-way merge silently takes main's reverted side and drops deferred work without a conflict. Checkout-sync keeps the base at the fork/last-sync-from-main point; synced paths become content-identical on both sides and auto-resolve later.
- Branch namespace is `aifamily/t<parent>` and dir `aiwork/t<parent>` (bare id — per-task dirs are always `t<id>_<slug>`, so no collision). The separate namespace keeps family branches invisible to the per-task `refs/heads/aitask/<task_name>` guards by construction.
- `family_worktree: true` frontmatter on the parent activates the mode. t1166_2 adds the write path; this task only **reads** the field (fixtures write it directly into test task files).

## Steps

1. **Scaffold `.aitask-scripts/aitask_family_worktree.sh`** — `#!/usr/bin/env bash`, `set -euo pipefail`, source `lib/terminal_compat.sh` + `lib/task_utils.sh` (read `aidocs/framework/shell_conventions.md` first, incl. the source-on-startup ↔ test-scaffold rule). Verb dispatch `case "$1"`. Shared resolution: task id (child `<p>_<n>` or parent `<p>`) → parent num → parent task file via `resolve_task_file` → `family_worktree` field read; derive `BRANCH=aifamily/t<p>`, `DIR=aiwork/t<p>`. Exit-code contract: 0 success / 1 usage-infra / 2 guarded refusal + `BLOCKED:<reason>` line (pattern: `aitask_archive.sh` gate_guard ~657-685).
2. **`status <task_id>`** (always exit 0): emit `FAMILY_MODE / PARENT / BRANCH / DIR / EXISTS / BRANCH_EXISTS / REMAINING_CHILDREN / REMAINING_LIST / AHEAD / BEHIND / DIRTY` (`AHEAD`/`BEHIND` via `git rev-list --count`; `DIRTY` via `git -C DIR status --porcelain`; `REMAINING_*` from parent `children_to_implement` via `read_yaml_list`). Then one `ACTIVE_SIBLING:<id>:<hostname>` line per *other* child that holds a lock (`aitask_lock.sh --check <sib>` — parse hostname) or whose frontmatter status is `Implementing`.
3. **`ensure <task_id> [--force]`**: refuse `BLOCKED:not_family_mode` when the flag is absent; refuse `BLOCKED:active_sibling:<id>:<hostname>` on any ACTIVE_SIBLING (skipped with `--force`). Then: dir+branch exist → `REUSED:<dir>`; branch without worktree → `git worktree add <dir> <branch>` → `REATTACHED:<dir>`; neither → `mkdir -p aiwork && git worktree add -b <branch> <dir> main` → `CREATED:<dir>`.
4. **`sync-from-main <task_id> [--keep-conflicts]`**: guards — family worktree exists, clean, no in-progress merge (write a code-side wedged-state check modeled on `assert_data_worktree_clean`, `lib/task_utils.sh:95-123`: probe `MERGE_HEAD`/`CHERRY_PICK_HEAD`/etc. in DIR). `git -C DIR merge main` → `UP_TO_DATE` / `SYNCED:<hash>`; on conflict default `git -C DIR merge --abort`, emit `CONFLICTS:<n>` + `CONFLICT_FILE:<path>` lines, exit 2; `--keep-conflicts` leaves the merge open.
5. **`diff-summary <task_id>`**: `git diff --name-status --no-renames main...<branch>` → `DIFF:<A|M|D>:<path>` + `TOTAL:<n>`. Read-only, no guards.
6. **`sync-paths <task_id> -- <path>...`**: guards (exit 2 each): root checkout on `main`; `git status --porcelain` clean at root; no wedged state at root; family worktree clean; each path present in diff-summary output (else emit `SKIPPED:<path>:not_in_diff` and continue with the rest — sync what is valid, refuse only if nothing valid remains). Apply per the diff letter: A/M → `git checkout <branch> -- <path>`; D → `git rm -r -- <path>`. Single commit: `t<task_id>: partial sync from family t<parent> (<k> paths)`. Emit `SYNCED_PATH:<letter>:<path>` lines + `COMMIT:<hash>`.
7. **`undo-sync <task_id> <commit>`**: guards — root on main, clean, not wedged. `<commit>` == `HEAD` and not on `origin/main` → `git reset --hard HEAD~1` → `ROLLED_BACK:<hash>`; otherwise → `git revert --no-edit <commit>` → `REVERTED:<hash>`.
8. **`final-merge <task_id> [--force]`**: refuse `BLOCKED:children_remaining:<csv>` while `REMAINING_CHILDREN > 0` (unless `--force`); root-on-main + clean + not-wedged guards; `git merge --no-ff <branch>` → `MERGED:<hash>` / `UP_TO_DATE`; conflicts handled as in sync-from-main (default abort fail-closed).
9. **`teardown <task_id> [--force]`**: refuse `BLOCKED:children_remaining:<csv>`; refuse `BLOCKED:unmerged_commits:<n>` when `git rev-list --count main..<branch>` > 0 (unless `--force`); `git worktree remove <dir>` (fallback `git worktree remove --force` + `rm -rf`) → `REMOVED_WORKTREE:<dir>`; `git branch -d <branch>` (`-D` under `--force`) → `REMOVED_BRANCH:<branch>`.
10. **`list`**: iterate `git for-each-ref refs/heads/aifamily/` → `FAMILY:<branch>:<ahead>:<worktree_attached>` lines (attached via `git worktree list --porcelain`).
11. **Whitelist (5 touchpoints)** per `aidocs/framework/aitasks_extension_points.md`: `.claude/settings.local.json` (`"Bash(./.aitask-scripts/aitask_family_worktree.sh:*)"`), `.codex/rules/default.rules`, `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json` (`"./.aitask-scripts/aitask_family_worktree.sh *": "allow"`). No `ait` dispatcher entry.
12. **Tests** — three self-contained bash files (assert helpers + PASS/FAIL summary, per existing tests/ conventions; scratch git repo fixture with a parent task file carrying `family_worktree: true` and children with `children_to_implement`):
    - `tests/test_family_worktree.sh` — happy paths (see task file Verification).
    - `tests/test_family_worktree_guards.sh` — every refusal + `--force` overrides + undo-sync branches (negative controls).
    - `tests/test_family_worktree_divergence.sh` — conflict-abort cleanliness; repeated partial syncs → clean final merge; main-side edit of a synced path + further family edit → conflict **surfaced** (the silent-loss regression pin).

## Verification

- `bash tests/test_family_worktree.sh && bash tests/test_family_worktree_guards.sh && bash tests/test_family_worktree_divergence.sh`
- `shellcheck .aitask-scripts/aitask_family_worktree.sh`
- Spike checkpoint: if any divergence test falsifies the checkout-sync model, STOP and re-plan t1166_3/4 with the parent task owner before proceeding.
