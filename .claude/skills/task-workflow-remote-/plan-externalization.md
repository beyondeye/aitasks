# Plan Externalization Procedure (Claude Code only)

This procedure copies the approved plan from Claude Code's **internal plan file** (`~/.claude/plans/<random-name>.md`) to the project's canonical external location in `aiplans/`. It is referenced from:

- `planning.md` Step 6 — proactive externalize right after `ExitPlanMode`.
- `SKILL.md` Step 8 — reactive safety fallback before the plan-file commit.

## Scope

**Run this only if running in Claude Code.** Other supported coding agents (OpenCode, Codex CLI, …) do not have an internal plan-mode file — they write plans directly to `aiplans/`, so there is nothing to externalize. When porting `task-workflow/` to those agent trees, omit this procedure file and its references in `planning.md` / `SKILL.md`.

## Background

Claude Code's `EnterPlanMode` writes the approved plan to `~/.claude/plans/<random-name>.md` (the exact path appears in the plan-mode system reminder you received when entering plan mode). `ExitPlanMode` does **not** copy the plan to `aiplans/` — that is your responsibility, and forgetting to do it causes the plan-file commit in Step 8 to fail with `pathspec 'aiplans/...' did not match any files`.

Prose reminders have historically been insufficient. Per the `feedback_guard_variables` memory, this procedure is expressed as an explicit bash command with structured output parsing, not just a sentence.

## Procedure

Run the externalize helper. **Step 6 (proactive, from `planning.md`) must pass `--force`**; **Step 8 (safety fallback, from `SKILL.md`) must not**. See the "When to use `--force`" note below.

**Both call-sites pass the resolved Step-5 branch context.** A profile path alone cannot describe it: the base branch may have been chosen interactively rather than read from the profile, and whether a worktree was created is a runtime fact.

- `--profile "aitasks/metadata/profiles/<active_profile_filename>"` — **only when `active_profile_filename` is set.** It is null on manual / resume invocations that carry no profile; passing a constructed path then would point at a file that does not exist, and the helper fails closed and aborts externalization. Omit the flag entirely in that case. When present, the helper reads `output_branch`, `base_branch` and `create_worktree` from it with a real YAML parser (so `output_branch: "dev"`, `'dev'` and `dev # comment` all resolve to `dev`), validates every scalar **inside the parser** before it is serialized, and fails closed on a missing, malformed or non-mapping file. Passing a *path* rather than a value keeps a user-authored branch name out of your command line.
- `--output-branch-default-file <path>` — when the base branch was chosen **interactively** rather than taken from the profile. Write the selected name to a scratch file with a **non-shell tool** (the Write tool), then pass the path. Do **not** use `--output-branch-default "<value>"` for an interactive answer: substituting it into a command line re-creates the injection sink, because git accepts refs like `release$(id -u)` and that expands *before* the helper can validate anything — even inside double quotes. Keep the scratch file until **Step 8** has run — Step 8 reuses the same `<branch-flags>`. Delete it only after Step 8 reaches a terminal result. (A no-op Step 8 tolerates a missing file and still returns `PLAN_EXISTS`, but any call that actually writes the header needs it.)
- `--no-worktree` — when Step 5 worked on the current branch. `output_branch` does not apply outside worktree mode; this also clears any stale `Output branch:` already present in a plan's frontmatter, so a later session cannot consume it.

If the helper exits non-zero (unsafe branch name, unreadable profile, empty value file), **stop** — do not fall back to a default and do not continue to Step 9.

`--output-branch <name>` and `--output-branch-default <name>` remain available for values already known to be shell-safe (e.g. resolved from a profile by other tooling); both are validated identically.

Passing these in Step 6 only is **not** sufficient: Step 8 is the one call that builds the header when Step 6 was skipped or returned `NOT_FOUND`, it runs immediately before Step 9 reads the header, and without them the configured merge target would be silently discarded.

Below, `<branch-flags>` stands for the resolution flags established above. Build it once, then reuse it verbatim in **every** invocation — including retries:

- With an active profile: `--profile "aitasks/metadata/profiles/<active_profile_filename>"`
- **Without one** (`active_profile_filename` is null — manual / resume invocations): omit `--profile` entirely. Do **not** construct a path from a null value; the helper fails closed on a missing profile and would abort externalization.
- Add `--output-branch-default-file <path>` when the base branch was chosen interactively.
- Add `--no-worktree` when Step 5 worked on the current branch.

Current-branch mode **always** includes `--no-worktree` — it is what tells the helper there is no merge target, and it is also what clears a stale `Output branch:` left in a plan's frontmatter by an earlier run. So the minimal set for a no-profile, current-branch invocation is `--no-worktree`, not an empty one. An empty `<branch-flags>` is only correct for a bare backward-compatible helper call that makes no claim about the merge target at all.

Step 6 form (proactive, after `ExitPlanMode`):

```bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id> --force <branch-flags>
```

Step 8 form (safety fallback, idempotent):

```bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id> <branch-flags>
```

If you still remember the exact internal plan path from the plan-mode system reminder, pass it explicitly to skip the auto-scan (combine with `--force` in Step 6 as needed):

```bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id> --internal <path> --force <branch-flags>
```

Concrete example — the shipped `fast.yaml`, which sets `create_worktree: false` and no `base_branch`, so it is a current-branch profile:

```bash
./.aitask-scripts/aitask_plan_externalize.sh 42 --force \
  --profile "aitasks/metadata/profiles/fast.yaml" --no-worktree
```

Concrete example — a worktree profile that sets `output_branch`:

```bash
./.aitask-scripts/aitask_plan_externalize.sh 42 --force \
  --profile "aitasks/metadata/profiles/integration.yaml"
```

Concrete example — no active profile, current branch (minimal `<branch-flags>` is `--no-worktree`):

```bash
./.aitask-scripts/aitask_plan_externalize.sh 42 --force --no-worktree
```

**Parse the output** (exactly one line, exit 0 in all non-argument-error cases):

- `PLAN_EXISTS:<path>` — already externalized (e.g., the Step 8 safety call after a successful Step 6 externalization). No action needed. Only emitted when `--force` is **not** passed.
- `EXTERNALIZED:<external>:<source>` — copied successfully (no existing file was overwritten). Proceed.
- `OVERWRITTEN:<external>:<source>` — existing external plan was replaced with the current internal plan (only possible when `--force` is passed). Treat identically to `EXTERNALIZED` — proceed to commit.
- `MULTIPLE_CANDIDATES:<p1>|<p2>|...` — multiple internal plan files fall within the recent-activity window. Use `AskUserQuestion` to let the user pick the right one (header: "Plan source"), then re-run with `--internal <chosen>`, **preserving `--force` and the full `<branch-flags>` from the original call**. Dropping them on the retry is silent and costly: the retry is the call that actually writes the header, so the configured merge target would be replaced by the repository primary and Step 9 would merge to the wrong branch. Keep the `--output-branch-default-file` scratch file in place until the procedure reaches a terminal result (`EXTERNALIZED` / `OVERWRITTEN` / `PLAN_EXISTS` / `NOT_FOUND`), recreating it if it was already removed.
- `NOT_FOUND:<reason>` — handle per reason:
  - `no_internal_files` — no recent internal plan was found. In Step 6, write the plan manually with the Write tool using the naming convention and metadata header in `planning.md`. In Step 8 (safety fallback), warn the user: "No plan file exists in `aiplans/` and no recent internal plan was found. The implementation will be committed without a plan file update." and skip the consolidation/plan-commit sub-steps. Note: when `--force` is combined with this reason, the existing external plan file (if any) is left untouched.
  - `no_internal_dir` — `~/.claude/plans/` is missing. Same handling as `no_internal_files`.
  - `source_not_file` — the `--internal` path is wrong; re-run without it (or correct the path).
  - `no_task_file` — task id could not be resolved to a task filename; check the id and retry.

## When to use `--force`

- **Step 6 (proactive, from `planning.md`):** always pass `--force`. Step 6 runs immediately after `ExitPlanMode`, so the internal plan file is the new source of truth and must replace any pre-existing external plan (e.g., the "Verify plan" path in §6.0, or a child task whose profile sets `plan_preference_child: verify`). Without `--force` the script short-circuits with `PLAN_EXISTS` and the revisions never reach `aiplans/`.
- **Step 8 (safety fallback, from `SKILL.md`):** never pass `--force`. Step 8 is purely reactive — if the plan was already externalized in Step 6, leave it alone. `PLAN_EXISTS` is the expected outcome and is a no-op.

## Commit the externalized plan (Step 6 only)

In Step 6 (proactive call), after a successful `EXTERNALIZED:` or `OVERWRITTEN:` result, commit the plan file separately from code changes (task/plan files use `./ait git`, not plain `git`, per CLAUDE.md):

```bash
./ait git add aiplans/<plan_file>
./ait git commit -m "ait: Add plan for t<task_id>"    # EXTERNALIZED
./ait git commit -m "ait: Update plan for t<task_id>" # OVERWRITTEN
```

Use `Add` when the external file did not exist before this call, and `Update` when `--force` replaced an existing one.

Step 8 handles its own plan commit as part of the "Commit changes" branch — do not double-commit.

## Encapsulation note

All `~/.claude/plans/` details — directory location, mtime-based recency filter, metadata-header construction, child-task sibling gathering — live inside `.aitask-scripts/aitask_plan_externalize.sh` (per `feedback_archive_encapsulation`). This procedure file only describes the caller's contract: what to invoke, how to parse the output, and what to do with each result.
