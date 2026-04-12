---
Task: t522_2_update_claude_code_callers.md
Parent Task: aitasks/t522_encapsulate_fold_logic_in_scripts.md
Sibling Tasks: aitasks/t522/t522_1_fold_scripts_and_tests.md, aitasks/t522/t522_3_mirror_caller_updates.md
Archived Sibling Plans: aiplans/archived/p522/p522_*_*.md
Worktree: (none — profile fast, create_worktree=false)
Branch: main
Base branch: main
---

# Plan: t522_2 Update Claude Code skill callers

## Context

Second child of t522. t522_1 shipped the three fold helper scripts (`aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`) and refactored two helpers into `lib/task_utils.sh`. This child migrates the five Claude Code skill callers to invoke the scripts directly instead of executing multi-step prose procedures, then reduces `task-fold-content.md` and `task-fold-marking.md` to thin reference documents.

Only `.claude/` is touched. Mirrors (`.agents/`, `.gemini/`, `.codex/`, `.opencode/`) are deferred to t522_3 so the Claude Code version can settle first as the canonical reference.

See the task description `aitasks/t522/t522_2_update_claude_code_callers.md` for the full caller-conversion templates.

## Implementation

### Step 1 — aitask-fold/SKILL.md

**Step 0b** (lines 32-56): replace the 25-line validate block with a 6-line `aitask_fold_validate.sh` invocation that parses `VALID:` / `INVALID:` lines. Abort if fewer than 2 valid tasks.

**Step 3** (lines 95-117): replace the two procedure invocations (content + marking) with two script calls:

```bash
./.aitask-scripts/aitask_fold_content.sh <primary_file> <folded_file1> ... \
  | ./.aitask-scripts/aitask_update.sh --batch <primary_num> --desc-file -
./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh <primary_num> <folded_id1> ...
```

### Step 2 — task-workflow/planning.md (Ad-Hoc Fold)

Shrink the Ad-Hoc Fold Procedure in Step 6.1 (lines 67-117) from ~50 lines to ~15 lines. Validation collapses to a single `aitask_fold_validate.sh --exclude-self <current_task_id>` call. Execute-fold collapses to the same two-script invocation as aitask-fold Step 3.

### Step 3 — aitask-explore/SKILL.md (Step 3)

**Line ~153** Content procedure reference → `aitask_fold_content.sh --primary-stdin` piped from a `printf` of the exploration-derived description; result used as the `description` argument to the Batch Task Creation Procedure.

**Line ~175** Marking procedure reference → `aitask_fold_mark.sh --commit-mode amend <new_task_num> <folded_ids>...` (amend because the fold marking should merge into the task-creation commit, not stand alone).

### Step 4 — aitask-pr-import/SKILL.md (Step 5)

Same substitutions as aitask-explore (lines ~236 and ~261). Commit mode `amend`.

### Step 5 — aitask-contribution-review/SKILL.md (Step 6)

Lines ~243-252 — two script calls, same pattern. `aitask_fold_content.sh --primary-stdin` piped into `aitask_update.sh --desc-file -` (primary task was just created by the contribution-review flow). `aitask_fold_mark.sh --commit-mode amend` follows.

### Step 6 — Reduce task-fold-content.md and task-fold-marking.md

Replace each file with a thin reference document:
- One-paragraph summary of what the script does
- Usage examples for both invocation modes (positional and `--primary-stdin` for content; `fresh` / `amend` / `none` for marking)
- Link to the script source (`../../../.aitask-scripts/aitask_fold_content.sh`, etc.)

Goal: 20 lines each (down from 63 and 92). Keep the files so existing in-repo links don't 404.

### Step 7 — Commit

```bash
git add .claude/skills/aitask-fold/SKILL.md \
        .claude/skills/task-workflow/planning.md \
        .claude/skills/task-workflow/task-fold-content.md \
        .claude/skills/task-workflow/task-fold-marking.md \
        .claude/skills/aitask-explore/SKILL.md \
        .claude/skills/aitask-pr-import/SKILL.md \
        .claude/skills/aitask-contribution-review/SKILL.md
git commit -m "chore: Migrate fold callers to new helper scripts (t522_2)"
```

## Verification

1. Re-run t522_1 tests to confirm no script-side regression:
   ```bash
   bash tests/test_fold_validate.sh && bash tests/test_fold_content.sh && bash tests/test_fold_mark.sh
   ```
2. `grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .claude/` — matches should appear only in the two reduced reference documents. No SKILL.md should still name-call the procedures.
3. Manual smoke-test: pick two Ready parent tasks in a temp worktree and run `/aitask-fold <id1> <id2>`. Verify the fold completes end-to-end without human-executed sub-procedures.

## Notes for sibling task (t522_3)

- Use the commit diff from this child as the authoritative reference for mirror ports.
- Every SKILL.md edit here needs to be mirrored in `.agents/skills/<skill>/SKILL.md`. Command wrappers in `.gemini/commands/` and `.opencode/commands/` may or may not need updates depending on whether they inline procedural steps.
- The reduced `task-fold-content.md` / `task-fold-marking.md` are NOT mirrored into `.agents/`, `.gemini/`, `.codex/`, `.opencode/`, so their reduction creates zero mirror work.
- Script paths (`./.aitask-scripts/aitask_fold_*.sh`) are identical across all frontends since scripts live outside `.claude/`.

## Final Implementation Notes

- **Actual work done:** Migrated all five Claude Code skill callers (aitask-fold, task-workflow/planning.md, aitask-explore, aitask-pr-import, aitask-contribution-review) to invoke `aitask_fold_validate.sh` / `aitask_fold_content.sh` / `aitask_fold_mark.sh` directly. Reduced `task-fold-content.md` from 62 → 25 lines and `task-fold-marking.md` from 92 → 22 lines to thin reference docs pointing at the scripts.

- **Deviations from plan:** None. Verification before implementation (Explore agent) confirmed script interfaces, caller line numbers, and procedure-reference locations exactly matched the plan. Line-number drift (aitask-fold +1-2, aitask-contribution-review +4) was handled by visual search with no semantic impact.

- **Issues encountered:**
  - `task-fold-marking.md` ends in a `## Step 6: Commit` block where a final fenced code block was dangling without a newline. The Read tool showed this as a line-93 truncation rather than a syntax error, and the Write replacement made it moot.
  - Three leftover `"Task Fold ... Procedure"` references remain in Notes sections: `aitask-fold/SKILL.md:138`, `aitask-explore/SKILL.md:244`, `aitask-pr-import/SKILL.md:321`. All three are in `## Notes` (prose descriptions), not executable procedure calls. The plan's verification step 3 explicitly allows "tangential historical notes" to keep the references, so they were left as-is. They can be freshened to script names in a follow-up if desired.
  - contribution-review used `fresh` commit mode previously. Switched to `amend` per the plan so the fold marking merges into the preceding `aitask_update.sh --desc-file -` commit, reducing commit noise on the import path.

- **Key decisions:**
  - **Keep positional form for aitask-fold Step 3** (not `--primary-stdin`) — the primary task already exists and its file path is already resolved in the caller, so passing the file directly is simpler.
  - **Use `--commit-mode amend` for all three "create then fold" callers** (explore, pr-import, contribution-review). Previously aitask-fold itself was the only `fresh` caller and the others varied. Now the convention is: "fresh" for merging into an existing, already-on-disk primary; "amend" when the primary was just created/updated as part of the same workflow.
  - **Did not touch the three Notes-section references.** Rewriting them would be a doc-cleanup pass that's out of scope for "migrate executable calls to scripts."

- **Notes for sibling tasks (t522_3):**
  - Mirror this commit's SKILL.md edits verbatim into `.agents/skills/<skill>/SKILL.md`. The five target files are: `aitask-fold`, `aitask-explore`, `aitask-pr-import`, `aitask-contribution-review`, plus `.claude/skills/task-workflow/planning.md` (which mirrors to `.agents/skills/task-workflow/planning.md` if present, otherwise into the equivalent task-workflow location).
  - The reduced `task-fold-content.md` / `task-fold-marking.md` are NOT mirrored anywhere, so skip them.
  - Script paths (`./.aitask-scripts/aitask_fold_*.sh`) are identical across all frontends — the mirrored SKILLs can use the same invocation strings.
  - **Verification tip for t522_3:** After mirroring, run `grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .agents/ .gemini/ .codex/ .opencode/` — matches should only be in Notes sections or fold-content/fold-marking reference docs (if the mirror frontends keep them).
  - **Contribution-review semantics note:** The switch from `fresh` to `amend` for contribution-review is a real behavior change worth calling out in the mirror commit message. Downstream users may notice one fewer commit per import.
  - **Fold tests are the regression gate:** `tests/test_fold_validate.sh`, `test_fold_content.sh`, `test_fold_mark.sh` all pass (7/7 + 16/16 + 26/26 = 49 assertions). Sibling mirrors should not touch the scripts or the test files, so they should keep passing.
