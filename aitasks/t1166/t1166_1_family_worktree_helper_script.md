---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, git-integration, child_tasks]
gates: [risk_evaluated]
anchor: 1166
created_at: 2026-07-20 12:05
updated_at: 2026-07-20 12:05
---

## Context

First child of t1166 (shared family worktree for child-task families) and the **riskiest spike, deliberately first**: it builds and proves the entire git mechanics layer as a standalone, unit-tested helper before any workflow prose consumes it. If the partial-sync model is falsified here, t1166_3/t1166_4 re-plan.

A "family worktree" is one long-lived worktree `aiwork/t<parent>` on branch `aifamily/t<parent>` (base `main`), shared by all children of a parent whose frontmatter has `family_worktree: true` (field added by t1166_2 — until it lands, tests can write the field directly into fixture task files; the helper only reads it). Key design decisions (pinned in the parent plan `aiplans/p1166_shared_worktree_for_child_task_families.md`):

- **Partial sync mechanics = per-path checkout onto main + one plain commit, NOT `merge --no-commit` + restore.** The merge-commit variant is silently lossy: a partial merge advances the merge base past ineligible changes, so the final merge drops them without a conflict. Checkout-sync keeps the base at the fork/last-sync point; synced paths become content-identical on both sides and auto-resolve at the final merge; repeated partial syncs compose.
- **Branch namespace `aifamily/` (not `aitask/`)** so per-task reuse guards and crash-recovery surveys never match family branches.
- **Hard concurrency guard:** a shared family worktree serializes child implementation. `ensure` refuses while another sibling holds a task lock or is `Implementing` (same-host AND cross-host — locks carry hostname).
- Exit-code contract: 0 success; 1 usage/infra error; 2 guarded refusal with a `BLOCKED:<reason>` line (mirrors `aitask_archive.sh` GATE_PENDING pattern).

## Key Files

- **NEW** `.aitask-scripts/aitask_family_worktree.sh` — the helper (all verbs below).
- **NEW** `tests/test_family_worktree.sh`, `tests/test_family_worktree_guards.sh`, `tests/test_family_worktree_divergence.sh`.
- Whitelist (5 touchpoints, per `aidocs/framework/aitasks_extension_points.md` "Adding a new helper script"): `.claude/settings.local.json`, `.codex/rules/default.rules`, `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`. No `ait` dispatcher entry (skill-facing helper).

## Reference Files for Patterns

- `.aitask-scripts/aitask_web_merge.sh` — structured `KEY:value` scan output, `set -euo pipefail`, lib sourcing.
- `.aitask-scripts/aitask_archive.sh` gate_guard (~657-685) — exit-2 + structured-line refusal pattern.
- `.aitask-scripts/lib/task_utils.sh` — `resolve_task_file`, wedged-merge-state detection (`assert_data_worktree_clean` shape; write a code-side analog), `read_yaml_list` for `children_to_implement`.
- `.aitask-scripts/aitask_lock.sh --check` — lock owner/hostname output for the sibling guard.
- `aidocs/framework/shell_conventions.md` — shebang, error helpers, `sed_inplace`, test scaffold rule.

## Implementation Plan (verb contracts — PINNED)

- `status <task_id>` (always exit 0): `FAMILY_MODE:true|false`, `PARENT:<num>`, `BRANCH:aifamily/t<num>`, `DIR:aiwork/t<num>`, `EXISTS:`, `BRANCH_EXISTS:`, `REMAINING_CHILDREN:<n>`, `REMAINING_LIST:<csv>`, `AHEAD:`, `BEHIND:`, `DIRTY:`, plus `ACTIVE_SIBLING:<id>:<hostname>` per other locked/Implementing child.
- `ensure <task_id> [--force]`: `REUSED:` / `REATTACHED:` (branch survived lost worktree → `git worktree add aiwork/t<N> aifamily/t<N>`) / `CREATED:` (`git worktree add -b aifamily/t<N> aiwork/t<N> main`). Refuses `BLOCKED:not_family_mode` without the flag; refuses `BLOCKED:active_sibling:<id>:<hostname>` on the concurrency guard (`--force` overrides).
- `sync-from-main <task_id> [--keep-conflicts]`: merge main into family branch. `UP_TO_DATE` / `SYNCED:<hash>`; conflicts default to fail-closed abort (`CONFLICTS:<n>` + `CONFLICT_FILE:<path>` lines, exit 2); `--keep-conflicts` leaves merge in progress.
- `diff-summary <task_id>`: `git diff --name-status --no-renames main...aifamily/t<N>` → `DIFF:<A|M|D>:<path>` lines + `TOTAL:<n>`. Read-only.
- `sync-paths <task_id> -- <path>...`: guards (exit 2): root on main + clean, no wedged state, family worktree clean, path in diff (else `SKIPPED:<path>:not_in_diff`). A/M → `git checkout aifamily/t<N> -- <path>`; D → `git rm -r -- <path>`; single commit `t<task_id>: partial sync from family t<parent> (<k> paths)`. Output `SYNCED_PATH:<A|M|D>:<path>` lines + `COMMIT:<hash>`.
- `undo-sync <task_id> <commit>`: rollback after failed main-side verification. `<commit>` == HEAD on main and unpushed → `git reset --hard HEAD~1` (`ROLLED_BACK:<hash>`); HEAD moved or pushed → `git revert --no-edit` (`REVERTED:<hash>`); refuses on dirty/wedged state.
- `final-merge <task_id> [--force]`: refuses while children remain (`BLOCKED:children_remaining:<csv>`); `git merge --no-ff aifamily/t<N>` → `MERGED:<hash>` / `UP_TO_DATE`; conflicts as sync-from-main.
- `teardown <task_id> [--force]`: refuses while children remain or `BLOCKED:unmerged_commits:<n>`; then `git worktree remove` (+ `rm -rf` fallback) + `git branch -d` → `REMOVED_WORKTREE:` / `REMOVED_BRANCH:`.
- `list`: enumerate `aifamily/*` branches → `FAMILY:<branch>:<ahead>:<worktree_attached>` lines.

## Verification

- `bash tests/test_family_worktree.sh` — status resolution (family + non-family), ensure create/reuse/reattach, diff-summary A/M/D, sync-paths add/modify/delete propagation + family branch untouched, final-merge clean + UP_TO_DATE after full partial sync, teardown happy path.
- `bash tests/test_family_worktree_guards.sh` — teardown/final-merge refuse with children remaining; teardown refuses on unmerged commits; sync-paths refusals (dirty/non-main root, wedged, dirty family tree, SKIPPED paths); ensure refuses without flag; ensure BLOCKED:active_sibling same-host + cross-host fixtures + --force override; undo-sync reset-vs-revert + refusals.
- `bash tests/test_family_worktree_divergence.sh` — conflict abort leaves clean tree; repeated partial syncs then clean final merge; main-side edit of a synced path + further family edit → conflict SURFACED (regression pin against the silent-loss class).
- `shellcheck .aitask-scripts/aitask_family_worktree.sh`.
