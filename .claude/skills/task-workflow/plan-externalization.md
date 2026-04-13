# Plan Externalization Procedure (Claude Code only)

This procedure copies the approved plan from Claude Code's **internal plan file** (`~/.claude/plans/<random-name>.md`) to the project's canonical external location in `aiplans/`. It is referenced from:

- `planning.md` Step 6 — proactive externalize right after `ExitPlanMode`.
- `SKILL.md` Step 8 — reactive safety fallback before the plan-file commit.

## Scope

**Run this only if running in Claude Code.** Other code agents (OpenCode, Codex CLI, Gemini CLI) do not have an internal plan-mode file — they write plans directly to `aiplans/`, so there is nothing to externalize. When porting `task-workflow/` to those agent trees, omit this procedure file and its references in `planning.md` / `SKILL.md`.

## Background

Claude Code's `EnterPlanMode` writes the approved plan to `~/.claude/plans/<random-name>.md` (the exact path appears in the plan-mode system reminder you received when entering plan mode). `ExitPlanMode` does **not** copy the plan to `aiplans/` — that is your responsibility, and forgetting to do it causes the plan-file commit in Step 8 to fail with `pathspec 'aiplans/...' did not match any files`.

Prose reminders have historically been insufficient. Per the `feedback_guard_variables` memory, this procedure is expressed as an explicit bash command with structured output parsing, not just a sentence.

## Procedure

Run the externalize helper:

```bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id>
```

If you still remember the exact internal plan path from the plan-mode system reminder, pass it explicitly to skip the auto-scan:

```bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id> --internal <path>
```

**Parse the output** (exactly one line, exit 0 in all non-argument-error cases):

- `PLAN_EXISTS:<path>` — already externalized (e.g., "Verify plan" path in Step 6.0, or the Step 8 safety call after a successful Step 6 externalization). No action needed.
- `EXTERNALIZED:<external>:<source>` — copied successfully. Proceed.
- `MULTIPLE_CANDIDATES:<p1>|<p2>|...` — multiple internal plan files fall within the recent-activity window. Use `AskUserQuestion` to let the user pick the right one (header: "Plan source"), then re-run with `--internal <chosen>`.
- `NOT_FOUND:<reason>` — handle per reason:
  - `no_internal_files` — no recent internal plan was found. In Step 6, write the plan manually with the Write tool using the naming convention and metadata header in `planning.md`. In Step 8 (safety fallback), warn the user: "No plan file exists in `aiplans/` and no recent internal plan was found. The implementation will be committed without a plan file update." and skip the consolidation/plan-commit sub-steps.
  - `no_internal_dir` — `~/.claude/plans/` is missing. Same handling as `no_internal_files`.
  - `source_not_file` — the `--internal` path is wrong; re-run without it (or correct the path).
  - `no_task_file` — task id could not be resolved to a task filename; check the id and retry.

## Commit the externalized plan (Step 6 only)

In Step 6 (proactive call), after a successful `EXTERNALIZED:` or `PLAN_EXISTS:` result, commit the plan file separately from code changes (task/plan files use `./ait git`, not plain `git`, per CLAUDE.md):

```bash
./ait git add aiplans/<plan_file>
./ait git commit -m "ait: Add plan for t<task_id>"
```

Step 8 handles its own plan commit as part of the "Commit changes" branch — do not double-commit.

## Encapsulation note

All `~/.claude/plans/` details — directory location, mtime-based recency filter, metadata-header construction, child-task sibling gathering — live inside `.aitask-scripts/aitask_plan_externalize.sh` (per `feedback_archive_encapsulation`). This procedure file only describes the caller's contract: what to invoke, how to parse the output, and what to do with each result.
