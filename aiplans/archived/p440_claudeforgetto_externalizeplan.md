---
Task: t440_claudeforgetto_externalizeplan.md
Base branch: main
---

# Plan: Fix Claude Code plan externalization gap (t440)

## Context

**Problem.** The task-workflow skill instructs the model, right after
`ExitPlanMode`, to save the approved plan to `aiplans/p<N>_<name>.md`. In
practice, Claude Code writes the plan body to its *internal* plan file
(`~/.claude/plans/<random>.md`) during plan mode and frequently forgets to
copy it out to `aiplans/` before moving on to implementation. The failure
only surfaces in Step 8 when `./ait git add aiplans/<plan_file>` fails with
`pathspec did not match any files`. This has been observed repeatedly (see
t440 description — a real t441 run ended with Claude manually `cp`ing
`~/.claude/plans/refactored-baking-newt.md` to recover).

**Why this is Claude-Code–specific.** OpenCode writes plans directly to
external files (no internal plan mode). Gemini/Codex have no `task-workflow`
variant. Only Claude Code's `EnterPlanMode` has this indirection, so the
fix lives in `.claude/skills/task-workflow/`. The helper script is placed
in `.aitask-scripts/` (shared) but is invoked only from the Claude skill.

**Why prose instructions alone haven't been enough.** `planning.md` already
says "Immediately after the user approves the plan via `ExitPlanMode`, save
it to an external file." Claude Code still skips this step because after
`ExitPlanMode` the natural momentum is to jump to implementation. Per the
`feedback_guard_variables` memory, we need an **executable guard**, not
just a stronger sentence.

## Approach

Add **two safety nets** — one proactive, one reactive — both powered by a
single shared script:

1. **Proactive externalize step** right after `ExitPlanMode` in
   `planning.md`, invoked via an explicit bash call. This is the primary
   fix; the instruction becomes a concrete command, not a prose reminder.

2. **Reactive safety fallback** in `SKILL.md` Step 8 — at the "Consolidate
   the plan file" block and before the `./ait git add aiplans/` commit —
   re-runs the same script. If the proactive step was done, the script is
   a no-op (`PLAN_EXISTS`). If it was skipped, the script recovers from
   `~/.claude/plans/`.

Both call the new script `aitask_plan_externalize.sh`, so the recovery
logic lives in one place.

## Files to change

### 1. NEW: `.aitask-scripts/aitask_plan_externalize.sh`

Shared helper. Encapsulates all `~/.claude/plans/` details so they stay
out of SKILL.md (per `feedback_archive_encapsulation` — format details
belong in scripts, not skill files).

**Interface:**

```
Usage: aitask_plan_externalize.sh <task_id> [--internal <path>]

Arguments:
  <task_id>            Task number or child id (e.g., 16, 16_2, t16)
  --internal <path>    Optional explicit internal plan file path
                       (defaults to most-recent *.md in ~/.claude/plans/)

Output lines (exit 0 for success, non-zero only on argument errors):
  PLAN_EXISTS:<external_path>              Already externalized — no-op
  EXTERNALIZED:<external_path>:<source>    Copied from <source> to <external_path>
  NOT_FOUND:<reason>                       Could not externalize (details below)
  MULTIPLE_CANDIDATES:<path1>|<path2>|...  Ambiguous: multiple candidates within 1h

Reasons for NOT_FOUND:
  no_internal_dir      ~/.claude/plans/ does not exist
  no_internal_files    ~/.claude/plans/ is empty
  source_not_file      --internal path does not exist or is not a file
  no_task_file         Cannot resolve task id to a task filename
```

**Behavior:**

1. Resolve task id → external plan path and target task filename. Reuse
   the naming logic from `cmd_plan_file` in `aitask_query_files.sh`:
   - Parent: `aiplans/p<N>_<stem>.md` where `<stem>` is the task file stem
     minus the leading `t<N>_`.
   - Child: `aiplans/p<parent>/p<parent>_<child>_<stem>.md`.
   Use `resolve_task_file` / the existing `task-file` subcommand of
   `aitask_query_files.sh` to get the source task filename (this is the
   single source of truth for the stem).

2. If the external path already exists → emit `PLAN_EXISTS:<path>` and
   return 0. This is the no-op case — second invocation at Step 8 finds
   the file already in place.

3. Otherwise locate the source:
   - If `--internal <path>` was provided: use it verbatim. Fail with
     `NOT_FOUND:source_not_file` if the file does not exist.
   - Else scan `~/.claude/plans/` for `*.md` by mtime (newest first).
     Ignore files older than the task's `assigned_at` epoch when that is
     derivable, to avoid grabbing a stale plan from a prior session.
     Practical heuristic: **restrict to files with mtime within the last
     1 hour** (configurable via `AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS`, default
     3600). This avoids Claude's global plans directory (~1800 files
     observed in `~/.claude/plans/`) polluting the match.
   - If zero candidates → `NOT_FOUND:no_internal_files`.
   - If one candidate → use it.
   - If multiple candidates within the window → emit
     `MULTIPLE_CANDIDATES:<p1>|<p2>|...` and return 0. The caller decides
     (via `AskUserQuestion` in the skill).

4. Create target directory if needed (`mkdir -p aiplans/p<parent>/` for
   children). Read the internal plan file. Prepend the required metadata
   header *only if* the file does not already start with a `---` YAML
   frontmatter block. Header fields come from the task file and the
   current environment:
   - `Task:` — task filename (from resolution step).
   - `Parent Task:` / `Sibling Tasks:` / `Archived Sibling Plans:` —
     for child tasks, computed from the parent directory listing.
   - `Worktree:` — `aiwork/<task_name>` only if `aiwork/<task_name>/`
     exists; otherwise omit.
   - `Branch:` — current branch via `git symbolic-ref --short HEAD` if not
     `main`; otherwise omit.
   - `Base branch:` — `main` (matches current project convention).
   Write via a temp file + `mv` to avoid partial writes. Emit
   `EXTERNALIZED:<external_path>:<source>`.

5. All filesystem writes are confined to `aiplans/<...>`. The script
   never modifies files in `~/.claude/plans/`.

**Encapsulation rationale (per memory):** SKILL.md never mentions
`~/.claude/plans/`, `mtime`, or internal plan file details. Those live
exclusively in this script.

### 2. EDIT: `.claude/skills/task-workflow/planning.md`

**Section "Save Plan to External File" (line 171+).** Rewrite the opening
to be Claude-Code-explicit and command-driven. Replace the current single
sentence with:

```markdown
## Save Plan to External File

Claude Code's `EnterPlanMode` writes the approved plan to an **internal
plan file** at `~/.claude/plans/<random-name>.md` (the exact path was
shown in the plan-mode system reminder you received when entering plan
mode). The external `aiplans/` copy is **NOT** created automatically by
`ExitPlanMode`. You **MUST** externalize it now, before proceeding to
Step 7 (Implement).

Run the externalize helper immediately after `ExitPlanMode`:

\`\`\`bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id>
\`\`\`

If you still know the exact internal plan path from the plan-mode system
reminder, pass it explicitly to skip the heuristic scan:

\`\`\`bash
./.aitask-scripts/aitask_plan_externalize.sh <task_id> --internal <path>
\`\`\`

Parse the output:
- `PLAN_EXISTS:<path>` — already externalized (e.g., verify-plan path). Done.
- `EXTERNALIZED:<external>:<source>` — copied successfully. Proceed.
- `MULTIPLE_CANDIDATES:<p1>|<p2>|...` — ambiguous. Use `AskUserQuestion`
  to let the user pick the right one (header: "Plan source"), then re-run
  with `--internal <chosen>`.
- `NOT_FOUND:<reason>` — see the reason:
  - `no_internal_files` / `no_internal_dir` — write the plan manually
    with the Write tool using the naming convention below.
  - `source_not_file` — the `--internal` path is wrong; re-run without it.

**Commit the externalized plan** (task/plan files use `./ait git`, not
plain `git`, per CLAUDE.md):

\`\`\`bash
./ait git add aiplans/<plan_file>
./ait git commit -m "ait: Add plan for t<task_id>"
\`\`\`

(Keep the existing "File naming convention" and "Required metadata header"
subsections below — they remain the source of truth for the output format.)
```

The existing naming/metadata subsections stay as-is so that the
manual-fallback case still has a specification.

### 3. EDIT: `.claude/skills/task-workflow/SKILL.md` — Step 8

**Consolidate-the-plan-file block (line 274+).** Prepend a safety recovery
step:

```markdown
  - **Verify the plan file exists externally (Claude Code safety):** Before
    reading/updating the plan, run the externalize helper as a recovery
    fallback — it's a no-op if the plan was already externalized in Step 6:

    \`\`\`bash
    ./.aitask-scripts/aitask_plan_externalize.sh <task_id>
    \`\`\`

    Parse the output as in Step 6. If `NOT_FOUND:no_internal_files`, warn
    the user: "No plan file exists in `aiplans/` and no recent internal
    plan was found. The implementation will be committed without a plan
    file update." and skip the consolidation/plan-commit sub-steps below.
    If `MULTIPLE_CANDIDATES`, handle as in Step 6 and re-run with
    `--internal`.

  - **Consolidate the plan file** before committing:
    - ...
```

No other changes to Step 8 — the existing `./ait git add aiplans/<plan_file>`
block now runs against a guaranteed-present file.

### 4. NEW: `tests/test_plan_externalize.sh`

Follow the project test style (`tests/test_archive_utils.sh` as template):
self-contained, uses `assert_eq` / `assert_contains`, prints PASS/FAIL
summary, exits non-zero on failure. Create a sandbox with:

- A fake `aitasks/t999_sandbox_task.md` (minimal frontmatter).
- A fake `HOME` pointing at `$TMPDIR/fakehome` with
  `fakehome/.claude/plans/one-recent.md` + `stale-old.md` (mtime 2h ago).

Test cases:
1. `aitask_plan_externalize.sh 999` → `EXTERNALIZED:aiplans/p999_sandbox_task.md:.../one-recent.md`; target file exists and has the metadata header prepended.
2. Second invocation → `PLAN_EXISTS:aiplans/p999_sandbox_task.md` (idempotent no-op).
3. Remove the fresh file, leave only `stale-old.md` → `NOT_FOUND:no_internal_files` (age filter works).
4. Two recent files → `MULTIPLE_CANDIDATES:...|...`.
5. Explicit `--internal /path/to/fresh.md` → `EXTERNALIZED:...`, and `--internal /nonexistent` → `NOT_FOUND:source_not_file`.
6. Child task form `999_2` with a pre-created `aitasks/t999/t999_2_sub.md` → external path is `aiplans/p999/p999_2_sub.md` and the parent dir is created.
7. Internal plan that already starts with `---` YAML → header is NOT duplicated.

Run from project root (no network, no git commits). Test wires
`AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS` to verify the age-filter knob.

### 5. Add to `CLAUDE.md` test list

Append `bash tests/test_plan_externalize.sh` to the testing block in
`CLAUDE.md` (line ~27 area — note: the user just added
`test_crew_setmode.sh` there, so keep the list grouped).

## Files NOT changed

- `aitask-pickrem` / `aitask-pickweb` — these are non-interactive Claude
  Code Web flows; per the aitask-pickweb skill, they avoid `EnterPlanMode`
  entirely and write plans directly. No externalization gap.
- `.opencode/`, `.gemini/`, `.agents/` variants — they don't use
  `EnterPlanMode`, so the bug doesn't exist there (confirmed by the
  exploration agent). A follow-up aitask should still be suggested so
  the user can decide whether to port this fix; noted in the Step 9
  final-notes prompt, not in this implementation.
- `aitask_query_files.sh` — deliberately not extended. The new script
  *uses* its `task-file` subcommand to resolve the stem, but the
  externalize logic is a new concern (writes files, reads `$HOME`) that
  doesn't belong in a read-only query script.

## Verification

1. **Unit test:** `bash tests/test_plan_externalize.sh` (all 7 cases
   pass).
2. **Shellcheck:** `shellcheck .aitask-scripts/aitask_plan_externalize.sh`
   passes cleanly.
3. **End-to-end (this task itself):** Steps 6–8 of the workflow will run
   the new script on t440. If this task commits successfully without a
   manual `cp` workaround, the fix is verified in production. Include
   this observation in Final Implementation Notes.
4. **Idempotency:** Re-running the Step-8 safety call on an
   already-externalized plan emits `PLAN_EXISTS:...` and exits 0 — the
   Step 8 commit then proceeds normally.
5. **Negative path:** Temporarily rename the Step-6 externalize call in
   a scratch branch, run a small task through; confirm the Step-8
   fallback recovers the plan from `~/.claude/plans/`.

## Follow-ups (out of scope for t440)

After this task lands, suggest the user create separate aitasks to:
- Mirror the planning.md / SKILL.md changes into `.gemini/skills/`,
  `.agents/skills/`, `.opencode/skills/` **if** those agents ever start
  using an internal-plan-file pattern. Currently they don't, so these
  are informational follow-ups only.
- Extend the script to optionally compare the internal and external plan
  file mtimes and warn if the internal one is newer (i.e., Claude edited
  the internal plan after externalization). This is a stretch goal,
  not required for the core bug fix.

## Step 9 reminder

Per task-workflow Step 9, after implementation this plan file itself will
be updated with "Final Implementation Notes" capturing deviations, then
committed via `./ait git commit -m "ait: Update plan for t440"`, then
archived via `./.aitask-scripts/aitask_archive.sh 440`, then pushed via
`./ait git push` (both `git push` and `./ait git push` if branches
differ).

## Final Implementation Notes

- **Actual work done:**
  1. Created `.aitask-scripts/aitask_plan_externalize.sh` (shared helper, executable, shellcheck-clean). Encapsulates all `~/.claude/plans/` details — task id resolution, mtime-based recency filter, metadata-header construction (including child-task Parent/Sibling/Archived Sibling Plans fields), atomic temp-file write + rename. Supports `--internal <path>` override and env-var overrides `AIT_PLAN_EXTERNALIZE_INTERNAL_DIR` / `AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS`.
  2. Created `.claude/skills/task-workflow/plan-externalization.md` — dedicated Claude-Code-only procedure file describing invocation, output parsing (`PLAN_EXISTS` / `EXTERNALIZED` / `MULTIPLE_CANDIDATES` / `NOT_FOUND:<reason>`), and recovery guidance.
  3. Edited `.claude/skills/task-workflow/planning.md` "Save Plan to External File" section — replaced the one-sentence reminder with a short conditional wrapper that references `plan-externalization.md` only for Claude Code, kept the existing naming/metadata subsections as the manual-fallback spec and source of truth for the file format.
  4. Edited `.claude/skills/task-workflow/SKILL.md` Step 8 — prepended a one-paragraph "Verify the plan file exists externally (Claude Code only)" step that also references `plan-externalization.md`. Added the new procedure to the "Procedures" list at the bottom of SKILL.md.
  5. Wrote `tests/test_plan_externalize.sh` with 19 assertions across 9 cases (fresh, idempotent, stale-ignored, multiple, --internal ok/nonexistent, child task, existing-frontmatter-not-duplicated, age-window env var, unknown-task-id). All pass.
  6. Appended `bash tests/test_plan_externalize.sh` to the test list in `CLAUDE.md`.

- **Deviations from plan:**
  1. **Procedure extraction (user feedback during Step 7).** The original plan put the expanded externalize instructions directly in `planning.md` Step 6 and in SKILL.md Step 8. The user corrected this mid-implementation: extract the full procedure into a dedicated `plan-externalization.md` file and keep only a short conditional "if running in Claude Code" wrapper in the shared files, so the port to `.opencode/`, `.gemini/`, `.agents/` trees can obviously drop the procedure file. This is captured as a new feedback memory `feedback_agent_specific_procedures.md` for future sessions. Net effect: one extra file (`plan-externalization.md`), and the edits in `planning.md` / `SKILL.md` are much shorter than originally planned.
  2. **Test count (9 cases, 19 assertions instead of 7 cases).** Added two beyond the original plan: (a) `AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS` widened-window case — verifies the env-var knob works; (b) unknown task id → `NOT_FOUND:no_task_file` — verifies the task-not-resolved path.
  3. **`MULTIPLE_CANDIDATES` ordering.** The plan did not specify an order for the emitted candidate list. The script sorts newest-first by mtime (descending), so the user sees the most recently-written plan first when disambiguating. Not called out in the plan but a natural UX choice.

- **Issues encountered:**
  1. **shellcheck SC1091 from project root.** `shellcheck -x` from the project root can't follow `# shellcheck source=lib/terminal_compat.sh` because the relative path is resolved from `$PWD` rather than the script's own directory. This is an info-level notice (not an error) and matches how every other `.aitask-scripts/aitask_*.sh` behaves when linted from the repo root. `shellcheck --severity=error` passes cleanly; `cd .aitask-scripts && shellcheck -x aitask_plan_externalize.sh` also passes cleanly. No code change needed.

- **Key decisions:**
  1. **Portable `stat` for mtime.** The script tries `stat -c %Y` (GNU/Linux) first, falls back to `stat -f %m` (BSD/macOS). Uses integer arithmetic for the age-window comparison to avoid `find -mtime`'s day-granularity limitation.
  2. **Age-window approach over "newer than task assigned_at".** The plan mentioned "files older than the task's `assigned_at` epoch when that is derivable" as a conceptual filter; the implementation uses a flat `MAX_AGE_SECS` window (default 3600s, configurable via env var). Simpler, no task-frontmatter parsing, and works uniformly for the proactive (Step 6) and reactive (Step 8) call sites. Plan's rationale about avoiding Claude's ~1800-file global plans directory is preserved.
  3. **Candidate list joined with `|` not newlines.** `MULTIPLE_CANDIDATES` is emitted as a single line `MULTIPLE_CANDIDATES:p1|p2|...` so the caller can split on `|` after stripping the prefix — matches the existing convention for multi-value structured outputs elsewhere in `.aitask-scripts/`.
  4. **Metadata header is additive, not corrective.** If the internal plan already starts with `---` YAML frontmatter, the script copies it verbatim and does NOT prepend another header (test case 7 enforces this). Prevents duplicate headers if the user or a previous run already populated the metadata.
  5. **Atomic write via temp file + `mv`.** All file writes go through `mktemp` + `mv` within the same filesystem (`${TMPDIR:-/tmp}`) to avoid partial writes on interruption.
  6. **No `./ait git` inside the helper.** The helper only creates the file in `aiplans/`; committing it is the caller's responsibility (documented in `plan-externalization.md`). Keeps the helper re-usable from any call site without coupling to the ait-git routing.

- **End-to-end verification of the fix on this very task.** The Step 8 safety-recovery call on t440 itself returned `PLAN_EXISTS:aiplans/p440_claudeforgetto_externalizeplan.md` (correct: the plan was pre-existing from a prior planning session and was not re-authored via EnterPlanMode during this run, so `plan_preference: use_current` in the `fast` profile skipped Step 6.1). The commit of this plan file therefore proceeds against a guaranteed-present file, demonstrating the idempotent-no-op branch end-to-end.

- **Follow-ups (for separate aitasks, out of scope for t440):**
  1. Mirror the `plan-externalization.md` reference into `.opencode/skills/`, `.agents/skills/` (codex cli), `.gemini/skills/` variants of `task-workflow/` — though per the procedure scope note, those agent trees should NOT copy the procedure file itself because the underlying bug (internal plan file indirection) does not exist in those agents. Suggest explicit "do not port" follow-ups rather than silent omission.
  2. Optionally extend the script to compare internal-vs-external plan file mtimes and warn if the internal one is newer (indicating Claude edited the plan after externalization). Stretch goal only.
