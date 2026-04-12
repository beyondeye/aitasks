---
Task: t522_encapsulate_fold_logic_in_scripts.md
Worktree: (none — profile fast, create_worktree=false)
Branch: main
Base branch: main
---

# Plan: t522 Encapsulate fold logic in scripts (parent)

## Context

Fold-related logic is currently scattered across four markdown procedures that Claude must execute as prose:

1. `.claude/skills/task-workflow/task-fold-content.md` — build merged description body (pure prose, no shell commands)
2. `.claude/skills/task-workflow/task-fold-marking.md` — 6 steps: read existing, handle transitive, set `folded_tasks`, update each folded task, Step 4b parent-cleanup for child task IDs, commit
3. `.claude/skills/task-workflow/planning.md` Ad-Hoc Fold Procedure (Step 6.1) — validate + content + marking
4. `.claude/skills/aitask-fold/SKILL.md` Step 0b — validation (task file resolve, status check, children check)

Duplication confirmed during exploration:

- Validation logic duplicated between `aitask-fold/SKILL.md:32-52` and `planning.md:85-93` (nearly identical).
- Parent-cleanup logic (Step 4b) duplicated between `task-fold-marking.md` and `aitask_archive.sh:349-354` (the `handle_folded_tasks` safety-net).
- Content-merging is prose-only; Claude re-implements the same filename-parsing, body-extraction, and header-building logic in each caller.
- Five callers (aitask-fold, aitask-explore, aitask-pr-import, aitask-contribution-review, planning.md) each run a multi-step recipe that has to stay in lock-step.

This parent task is split into three sequential children that deliver the scripts, migrate Claude Code callers, and mirror the caller updates into the other agent frontends.

## Child breakdown

Order: `t522_1 → t522_2 → t522_3`.

### t522_1 — Scripts + shared helpers + tests

Ships three new bash scripts (`aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`), moves `read_yaml_field` / `read_task_status` from `aitask_archive.sh:170-200` into `lib/task_utils.sh`, and adds three matching test files. No SKILL.md or procedure file changes — existing callers keep working on the untouched prose procedures until t522_2 lands.

See `aiplans/p522/p522_1_fold_scripts_and_tests.md` for details.

### t522_2 — Update Claude Code skill callers

Migrates five callers (`aitask-fold/SKILL.md`, `task-workflow/planning.md`, `aitask-explore/SKILL.md`, `aitask-pr-import/SKILL.md`, `aitask-contribution-review/SKILL.md`) to invoke the new scripts directly. Reduces `task-fold-content.md` and `task-fold-marking.md` to thin reference documents. Blocked by t522_1.

See `aiplans/p522/p522_2_update_claude_code_callers.md` for details.

### t522_3 — Mirror caller updates

Ports t522_2's `.claude/` edits into `.agents/`, `.gemini/`, `.codex/`, `.opencode/` (where relevant). The new bash scripts are shared across frontends — no script copies needed. Blocked by t522_2. Uses the t522_2 commit diff as the authoritative reference.

See `aiplans/p522/p522_3_mirror_caller_updates.md` for details.

## Shared design

### Script interfaces (locked by t522_1)

**`aitask_fold_validate.sh [--exclude-self <id>] <id1> [<id2> ...]`**
Output lines (exit 0 always):
- `VALID:<id>:<file_path>`
- `INVALID:<id>:{not_found|status_<status>|has_children|is_self}`

No `--exclude-children` flag — both `/aitask-fold` and the planning ad-hoc fold accept child task IDs as sources.

**`aitask_fold_content.sh <primary_task_file> <folded_file1> [...]`**
**`aitask_fold_content.sh --primary-stdin <folded_file1> [...]`**
Writes merged description body to stdout. Preserves primary body, appends `## Merged from t<N>: <name>` sections per folded task, appends `## Folded Tasks` reference section.

**`aitask_fold_mark.sh [--no-transitive] [--commit-mode fresh|amend|none] <primary_id> <folded_id1> [...]`**
Defaults: `--commit-mode fresh`, transitive handling on. Emits:
- `PRIMARY_UPDATED:<id>`
- `FOLDED:<id>`
- `TRANSITIVE:<id>`
- `CHILD_REMOVED:<parent>:<child>`
- `COMMITTED:<short_hash>` / `AMENDED` / `NO_COMMIT`

Uses `task_git` helper from `task_utils.sh`, not raw `git`.

### Refactor

`read_yaml_field()` and `read_task_status()` move from `.aitask-scripts/aitask_archive.sh:170-200` into `.aitask-scripts/lib/task_utils.sh`. `aitask_archive.sh` already sources `task_utils.sh`, so the shared versions get picked up automatically once the local copies are removed.

### Out of scope for the whole parent task

- Refactoring `handle_folded_tasks()` in `aitask_archive.sh` to share code with `aitask_fold_mark.sh`. The duplication is small (~5 lines of `--remove-child` logic) and archival has independent test coverage in `tests/test_archive_folded.sh`.
- Creating a unified `aitask_fold_apply.sh` combining validate + content + mark. The three-script composition is flexible enough for all five callers; a combined script would add awkward stdin/args mixing for "create-during" callers (aitask-explore, aitask-pr-import, aitask-contribution-review).

## Verification

Each child has its own verification section; at the parent level:
1. After t522_1: all three new test files PASS + `test_archive_folded.sh` still PASSes (regression check on the `read_yaml_field` move).
2. After t522_2: `grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .claude/` produces only reference-document hits. Smoke-test: manually run `/aitask-fold` on two scratch tasks to confirm end-to-end flow.
3. After t522_3: each mirror file diffs parallel to its `.claude/` counterpart.

## References

- Parent task file: `aitasks/t522_encapsulate_fold_logic_in_scripts.md`
- Triggered by: t520 (better folding support) — created the ad-hoc fold procedure and child-task Step 4b logic whose complexity this task offloads.
