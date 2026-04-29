---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [changelog, scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-29 06:43
updated_at: 2026-04-29 07:55
---

## Goal

Fix `aitask_changelog.sh --gather` so it does not abort mid-loop when a task in the commit range has no resolvable archive file in the working tree.

## Repro

From `main` on this repo, with `v0.19.1` as the latest tag:

```bash
./.aitask-scripts/aitask_changelog.sh --gather
```

Output truncates after `=== TASK t711 ===` (no `ISSUE_TYPE:` / `TITLE:` / `=== END ===` follow), exit code `1`.

t706/t707/t708/t709 emit fully because their archive files exist locally on `main`. t711's archive (`aitasks/archived/t711_macos_installation_subpage_terminal_compat.md`) was committed on `origin/aitask-data` (the data branch) and is not present on `main`'s working tree, so `resolve_task_file 711` fails.

`bash -x` trace shows the script reaches `task_file=` (empty) for t711, then jumps directly to `_ait_archive_cleanup` (the EXIT trap from `lib/task_utils.sh`) and exits.

## Root cause

`.aitask-scripts/aitask_changelog.sh:gather()`:

```bash
task_file=$(resolve_task_file "$task_id" 2>/dev/null || echo "")
```

`resolve_task_file` (in `lib/task_utils.sh`) calls `die "No task file found ..."` when the task is missing, and `die` calls `exit 1`. Because `die` is invoked inside the command-substitution subshell, `exit` terminates the subshell **before** the `|| echo ""` fallback gets a chance to run. The subshell ends with status 1, the assignment inherits that status, and the parent script's `set -e` then aborts the whole script.

The same pattern is on the very next line for `resolve_plan_file`. In our repro `resolve_plan_file` happened to return 0 for t711 (its plan still resolved through some other path), but the bug class is identical and would bite under different inputs.

## Possible solutions

The implementation task should pick one (and surface the others as a follow-up if they apply broadly).

**Option 1 — hotfix in the changelog script (smallest diff).**
Move the `||` outside the command substitution so it absorbs the subshell's exit status at the assignment level instead of inside the subshell:

```bash
task_file=$(resolve_task_file "$task_id" 2>/dev/null) || task_file=""
plan_file=$(resolve_plan_file "$task_id" 2>/dev/null) || plan_file=""
```

This fixes the immediate bug and unblocks every future changelog run. Two-line patch, no behavior change for tasks that resolve normally.

**Option 2 — soft / best-effort lookup in `lib/task_utils.sh` (cleaner, more invasive).**
Add a soft variant of `resolve_task_file` / `resolve_plan_file` that `return 1`s on miss instead of `die`-ing. Either a flag (`resolve_task_file --soft 711`) or a sibling function (`try_resolve_task_file`). The changelog script would then call the soft form. Worth the extra surface area only if other callers in the codebase have the same "best-effort lookup" shape and would benefit.

**Option 3 — fall back to data-branch history when the working tree has no archive (deepest fix).**
When `resolve_task_file` / `resolve_plan_file` finds nothing locally, read the file from `origin/aitask-data:aitasks/archived/<filename>` via `git show`. Addresses the underlying split-branch architecture (task data lives on `aitask-data`, source on `main`) instead of just the exit-status mishandling. Bigger change, but it's the only option that actually surfaces t711-style tasks in the changelog rather than silently skipping them.

## Recommendation

Option 1 as the hotfix in this task (immediately unblocks `/aitask-changelog`). If the planning step decides Option 2 or 3 is also worth doing, surface that as its own follow-up task — they are not strictly needed to make the gather script stop aborting.

## Acceptance

- `./.aitask-scripts/aitask_changelog.sh --gather` runs to completion against the current `main` (with v0.19.1 as base tag), emitting `=== TASK t711 === ... === END ===` with `TITLE: t711` (or whatever fallback the chosen option yields), and exits 0.
- Existing tasks with archives present (t706/t707/t708/t709) continue to emit their full structured output unchanged.
- No new shellcheck findings on `.aitask-scripts/aitask_changelog.sh` (and on `lib/task_utils.sh` if Options 2 or 3 touch it).
