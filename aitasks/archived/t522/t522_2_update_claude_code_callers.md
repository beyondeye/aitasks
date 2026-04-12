---
priority: medium
effort: medium
depends: [t522_1]
issue_type: chore
status: Done
labels: [aitask_fold, task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-12 09:55
updated_at: 2026-04-12 11:59
completed_at: 2026-04-12 11:59
---

## Context

This is the second child of parent t522 (encapsulate fold logic in scripts). Child t522_1 shipped three new bash scripts (`aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`) plus shared helpers and tests. This child migrates the five Claude Code skill callers to invoke those scripts directly, instead of executing multi-step prose procedures.

This child only touches `.claude/` and does **not** touch `.agents/`, `.gemini/`, `.codex/`, or `.opencode/` — t522_3 owns mirror updates so that Claude Code settles first as the reference implementation.

## Dependencies

- Blocked by t522_1. The three fold helper scripts must exist and pass tests before callers can rely on them.

## Key Files to Modify

**Skill callers (five files):**
- `.claude/skills/aitask-fold/SKILL.md` — Step 0b (lines ~32-56) and Step 3 (lines ~95-117)
- `.claude/skills/task-workflow/planning.md` — Ad-Hoc Fold Procedure inside Step 6.1 (lines ~67-117)
- `.claude/skills/aitask-explore/SKILL.md` — Step 3 fold references (lines ~153 and ~175)
- `.claude/skills/aitask-pr-import/SKILL.md` — Step 5 fold references (lines ~236 and ~261)
- `.claude/skills/aitask-contribution-review/SKILL.md` — Step 6 fold references (lines ~243-252)

**Procedure files to reduce to thin pointer docs:**
- `.claude/skills/task-workflow/task-fold-content.md` — shrink from 63 lines to ~20 lines
- `.claude/skills/task-workflow/task-fold-marking.md` — shrink from 92 lines to ~20 lines

## Reference Files for Patterns

- **Parent plan:** `aiplans/p522_encapsulate_fold_logic_in_scripts.md` — full design context and caller conversion templates
- **Child t522_1 plan:** `aiplans/p522/p522_1_fold_scripts_and_tests.md` — script interfaces (what to invoke)
- **Committed fold scripts (source of truth for invocation patterns):**
  - `.aitask-scripts/aitask_fold_validate.sh`
  - `.aitask-scripts/aitask_fold_content.sh`
  - `.aitask-scripts/aitask_fold_mark.sh`
- **Example of a skill that already invokes a structured-output script:** `.claude/skills/aitask-pick/SKILL.md` Step 2b (calls `aitask_query_files.sh` and parses `HAS_CHILDREN:` / `NO_CHILDREN` lines) — mirror this exact parsing style.
- **Archive behavior preserved:** `.aitask-scripts/aitask_archive.sh` `handle_folded_tasks()` — this function is intentionally unchanged; do not touch it in this child either.

## Implementation Plan

### Step 1: aitask-fold/SKILL.md

**Step 0b** — replace the entire "Validate each task" / "Check remaining count" block (lines 32-56) with:

```markdown
- **Validate task IDs:** Run the fold validator and parse its structured output:
  ```bash
  ./.aitask-scripts/aitask_fold_validate.sh <id1> <id2> ...
  ```
  For each output line:
  - `VALID:<id>:<path>` — keep this task in the valid set.
  - `INVALID:<id>:<reason>` — warn "t<id>: <reason> — skipping" and exclude. `<reason>` values: `not_found`, `status_<status>`, `has_children`, `is_self`.
- **Check remaining count:** If fewer than 2 valid tasks remain, inform the user "Need at least 2 eligible tasks to fold. Only <N> valid task(s) found." and abort.
```

**Step 3** — replace Steps 3a-3c (content procedure invocation) and Steps 3d-3f (marking procedure invocation) with:

```markdown
### Step 3: Merge Content and Mark Folded Tasks

Merge the folded task content into the primary and update frontmatter in two script calls:

```bash
./.aitask-scripts/aitask_fold_content.sh <primary_file> <folded_file1> <folded_file2> ... \
  | ./.aitask-scripts/aitask_update.sh --batch <primary_num> --desc-file -

./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh <primary_num> <folded_id1> <folded_id2> ...
```

Parse the `aitask_fold_mark.sh` output for a `COMMITTED:<hash>` line confirming the fold was committed.
```

### Step 2: task-workflow/planning.md (Ad-Hoc Fold)

Replace the 6-step Ad-Hoc Fold Procedure (lines ~67-117) with a compact version:

```markdown
  **Ad-Hoc Fold Procedure:**

  1. **Parse the requested task IDs** from the description text or the user's message. Accept both parent IDs (plain number, e.g., `42`) and child IDs (`<parent>_<child>`, e.g., `16_2`).

  2. **Validate** — run the fold validator, excluding the current task:
     ```bash
     ./.aitask-scripts/aitask_fold_validate.sh --exclude-self <current_task_id> <id1> <id2> ...
     ```
     Parse `VALID:<id>:<path>` / `INVALID:<id>:<reason>` lines. Warn on each invalid entry.

  3. **Confirm** — If no valid tasks remain, continue planning without folding. Otherwise, present the list of valid tasks and use `AskUserQuestion`:
     - Question: "The following tasks will be folded into t<current>: <list>. Proceed?"
     - Header: "Fold"
     - Options: "Yes, fold them" / "No, skip folding"

  4. **Execute fold** (only if user confirmed):
     ```bash
     ./.aitask-scripts/aitask_fold_content.sh <current_task_file> <folded_file1> <folded_file2> ... \
       | ./.aitask-scripts/aitask_update.sh --batch <current_task_id> --desc-file -

     ./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh <current_task_id> <folded_id1> <folded_id2> ...
     ```

  5. **Resume planning** — Re-read the updated task file to pick up the merged content, then continue planning with the enriched description.
```

### Step 3: aitask-explore/SKILL.md (Step 3)

**Line ~153** — replace the Task Fold Content Procedure reference with:

```markdown
**If folded_tasks is non-empty:** Build the merged description using `aitask_fold_content.sh` with `--primary-stdin` (the primary task does not exist yet):

```bash
merged_desc=$(printf '%s\n' "<primary description from exploration>" | \
  ./.aitask-scripts/aitask_fold_content.sh --primary-stdin <folded_file1> <folded_file2> ...)
```

Use `$merged_desc` as the `description` argument for the Batch Task Creation Procedure below.
```

**Line ~175** — replace the Task Fold Marking Procedure reference with:

```markdown
**If folded_tasks is non-empty**, mark the folded tasks using `aitask_fold_mark.sh` with `--commit-mode amend` so the marking folds into the task-creation commit:

```bash
./.aitask-scripts/aitask_fold_mark.sh --commit-mode amend <new_task_num> <folded_id1> <folded_id2> ...
```
```

### Step 4: aitask-pr-import/SKILL.md (Step 5)

Same substitutions as Step 3 above (content procedure → `--primary-stdin` fold_content; marking procedure → `--commit-mode amend` fold_mark). Lines ~236 and ~261.

### Step 5: aitask-contribution-review/SKILL.md (Step 6)

**Lines ~243-252** — replace the two procedure invocations with:

```bash
merged_desc=$(printf '%s\n' "<new task description>" | \
  ./.aitask-scripts/aitask_fold_content.sh --primary-stdin <folded_file1> ...)
./.aitask-scripts/aitask_update.sh --batch <new_task_num> --desc-file - <<<"$merged_desc"

./.aitask-scripts/aitask_fold_mark.sh --commit-mode amend <new_task_num> <folded_id1> ...
```

(Check the exact surrounding context when editing — the existing prose mentions using the merged description as an update to an already-created task, which matches the above pattern.)

### Step 6: Reduce task-fold-content.md and task-fold-marking.md

Replace each file with a thin reference document. Template for `task-fold-content.md`:

```markdown
# Task Fold Content (reference)

Building the merged description body is handled by `.aitask-scripts/aitask_fold_content.sh`. See that script for the canonical implementation.

## Usage

**Merging into an existing primary task** (aitask-fold, planning ad-hoc fold):
```bash
./.aitask-scripts/aitask_fold_content.sh <primary_task_file> <folded_file1> <folded_file2> ...
```

**Building content for a new primary task** (aitask-explore, aitask-pr-import, aitask-contribution-review):
```bash
printf '%s\n' "<description from exploration>" | \
  ./.aitask-scripts/aitask_fold_content.sh --primary-stdin <folded_file1> <folded_file2> ...
```

The script writes the merged description body to stdout in the same structured format that used to be constructed by hand:
- Primary body preserved at the top
- `## Merged from t<N>: <name>` section for each folded task
- `## Folded Tasks` reference section at the end

Callers typically pipe the output into `aitask_update.sh --batch <id> --desc-file -` (for existing primaries) or pass it as the `description` argument to the Batch Task Creation Procedure (for new primaries).
```

Apply the same treatment to `task-fold-marking.md`, pointing at `aitask_fold_mark.sh` and noting the three `--commit-mode` options (`fresh`, `amend`, `none`) and the `--no-transitive` flag.

### Step 7: Commit

Commit the skill and procedure file updates with plain `git` (these are code, not task data):

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

## Verification Steps

1. Re-run the fold helper tests from t522_1 to confirm no regressions:
   ```bash
   bash tests/test_fold_validate.sh && bash tests/test_fold_content.sh && bash tests/test_fold_mark.sh
   ```
2. Dry read-through of each updated file: every invocation of a fold script must match the interfaces documented in `.aitask-scripts/aitask_fold_*.sh --help`.
3. `grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .claude/` — after the migration, matches should only appear in the two reduced reference documents (`task-fold-content.md`, `task-fold-marking.md`) and possibly in tangential historical notes. No SKILL.md should still call the procedures by name.
4. Manual smoke test: pick two Ready parent tasks in a temp worktree and run `/aitask-fold <id1> <id2>`. Verify the fold completes end-to-end without human-executed sub-procedures.

## Notes for Sibling Tasks (t522_3)

- Use the diff of this child's commit as the reference for mirror updates in t522_3. Every edit made here to `.claude/skills/aitask-fold/SKILL.md` needs to be mirrored into `.agents/skills/aitask-fold/SKILL.md` (and similarly for the other four skills).
- The reduced `task-fold-content.md` and `task-fold-marking.md` files are NOT mirrored into `.agents/`, `.gemini/`, `.codex/`, or `.opencode/` (exploration confirmed this), so their reduction does not create mirror work for t522_3.
- Script path `./.aitask-scripts/aitask_fold_*.sh` is identical across all frontends (scripts live outside `.claude/`), so mirrors can invoke them with the same path.
