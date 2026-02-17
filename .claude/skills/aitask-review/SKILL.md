---
name: aitask-review
description: Review code using configurable review modes, then create tasks from findings.
---

## Workflow

### Step 0a: Select Execution Profile

Check for available execution profiles:

```bash
ls aitasks/metadata/profiles/*.yaml 2>/dev/null
```

**If no profiles found:** Skip this step (no profile active, all questions asked normally).

**If exactly one profile found:** Auto-load it and inform user: "Using execution profile: \<name\> (\<description\>)".

**If multiple profiles found:**

Read each profile's `name` and `description` fields. Use `AskUserQuestion`:
- Question: "Select an execution profile (pre-configured answers to reduce prompts):"
- Header: "Profile"
- Options:
  - Each profile: label = `name` field, description = `description` field
  - "No profile" (description: "Ask all questions interactively")

**If "No profile" selected:** Proceed with all questions asked normally (no active profile).

Store the selected profile in memory for use throughout remaining steps.

**Error handling:** If a profile file has invalid YAML, warn the user ("Profile '\<filename\>' has invalid format, skipping") and exclude it from the selection list.

### Step 0c: Sync with Remote (Best-effort)

Do a best-effort pull to ensure the local state is up to date:

```bash
git pull --ff-only --quiet 2>/dev/null || true
```

This is non-blocking — if it fails (e.g., no network, merge conflicts), continue silently.

Also run best-effort stale lock cleanup:

```bash
./aiscripts/aitask_lock.sh --cleanup 2>/dev/null || true
```

### Step 1: Review Setup

#### 1a. Target Selection

Use `AskUserQuestion` to determine the review scope:
- Question: "What code areas should be reviewed?"
- Header: "Target"
- Options:
  - "Specific paths" (description: "Enter file paths, directories, or glob patterns via Other")
  - "Recent changes" (description: "Review files changed in specific commits")
  - "Entire codebase" (description: "Review all source files")

**If "Specific paths":** The user enters paths via the "Other" free text input. Parse as space or comma-separated paths. Verify each path exists.

**If "Recent changes":**

1. **Fetch and filter commits in paginated batches of 10 relevant commits:**

   Fetch commits using `git log --oneline --shortstat` and filter out administrative task-handling commits whose messages start with the `ait:` prefix (case-insensitive):
   - `^ait: ` — all administrative commits (task creation, status changes, archival, updates, deletion, folding, changelog, version bumps, etc.)

   **Batch loading loop:** Keep fetching commits (increasing `--skip=<offset>`) until 10 non-filtered commits are collected for the current batch. Display each batch as a numbered list with diff stats:
   ```
   1. abc1234 Add feature X (+45/-12)
   2. def5678 Fix bug in Y (+3/-1)
   ...
   10. ghi9012 Refactor Z module (+120/-85)
   ```
   The `+N/-M` shows lines added/deleted, extracted from `--shortstat` output.

   Numbering continues across batches: first batch is 1-10, second is 11-20, etc.

2. Use `AskUserQuestion`: "Select commits to review:"
   - "Last 5 commits" (description: "Review changes from commits 1-5")
   - "Last 10 commits" (description: "Review changes from commits 1-10")
   - "Show 10 more commits" (description: "Load next batch of 10 relevant commits, starting from #<next_number>")
   - "Custom selection" (description: "Enter commit indices — ranges (1-5), specific (1,3,5), or mixed (1,2-4,7)")

   If "Show 10 more commits": fetch the next batch of 10 non-filtered commits, append to the displayed list, and re-present the selection question. Continue until the user makes a selection or no more commits are available.

3. If "Custom selection": user enters indices via "Other" free text input.
   Parse the input supporting: ranges (e.g., `1-5`), comma-separated (e.g., `1,3,5`), and mixed (e.g., `1, 2-4, 7`).
   Indices refer to the numbered commits displayed across all loaded batches.

4. Resolve selected commit indices to actual commit hashes, then get changed files:
   ```bash
   git diff --name-only <oldest_selected_hash>~1...<newest_selected_hash>
   ```
   For non-contiguous selections, union the file lists from each commit:
   ```bash
   git diff-tree --no-commit-id --name-only -r <hash>
   ```

**If "Entire codebase":** No filtering — review all source files in the project.

#### 1b. Review Mode Selection

List all `.md` files in `aitasks/metadata/reviewmodes/`:
```bash
ls aitasks/metadata/reviewmodes/*.md 2>/dev/null
```

Read each file's YAML frontmatter to extract `name`, `description`, and `environment` (optional list).

**Auto-detect project environment** by checking for:
- `pyproject.toml` or `setup.py` → `python`
- `build.gradle` or `build.gradle.kts` → `android`, `kotlin`
- `CMakeLists.txt` → `cpp`, `cmake`
- `package.json` → `javascript`, `typescript`
- `*.sh` scripts in project root or `aiscripts/` → `bash`, `shell`

**Sort modes** for display:
1. Environment-matching modes first (their `environment` list contains a detected environment)
2. Universal modes next (no `environment` field — these apply to any project)
3. Non-matching environment-specific modes last

**Profile check:** If the active profile has `review_default_modes` set (comma-separated list of mode names):
- Auto-select those modes. Display: "Profile '\<name\>': using review modes: \<mode list\>"
- Skip the AskUserQuestion below

Otherwise, present via `AskUserQuestion` multiSelect: "Select review modes to apply:"
- Each option: label = `name` from frontmatter, description = `description` from frontmatter
- Since `AskUserQuestion` supports max 4 options, implement pagination:
  - Show up to 3 modes per page + "Show more modes" if additional modes exist
  - On the last page, show up to 4 modes
  - Accumulate selections across pages before proceeding

#### 1c. Load Review Instructions

Read the full content of each selected review mode file. The markdown body after the YAML frontmatter contains the review instructions — these become the checklist for the automated review in Step 2.

### Step 2: Automated Review

For each selected review mode:

1. Read its review instructions (the markdown body after frontmatter)
2. Systematically explore the target paths following those instructions:
   - Use Glob to find relevant files within the target scope
   - Use Read to examine file contents
   - Use Grep to search for patterns mentioned in the review instructions
   - Use Task (Explore agents) for broader or deeper investigation when needed
3. Record each finding with:
   - **Mode:** The review mode name (e.g., "Code Conventions")
   - **Severity:** `high`, `medium`, or `low`
   - **Location:** `file_path:line_number`
   - **Description:** What the issue is
   - **Suggested fix:** How to address it

**Severity guidelines:**
- **High:** Security vulnerabilities, data loss risks, correctness bugs, broken functionality
- **Medium:** Code quality issues, missing error handling, performance concerns, inconsistent patterns
- **Low:** Style issues, minor naming inconsistencies, missing documentation, cosmetic improvements

### Step 3: Findings Presentation

**If no findings:** Inform user "No issues found across the selected review modes." and end the workflow.

**If findings exist:** Group findings by review mode, then by severity (high → medium → low). Present as markdown:

```
## Review Findings

### <Mode Name> (N findings)

**High severity:**
1. `file_path:line` — Description. *Suggested fix: ...*

**Medium severity:**
2. `file_path:line` — Description. *Suggested fix: ...*

**Low severity:**
3. `file_path:line` — Description. *Suggested fix: ...*

### <Next Mode> (N findings)
...
```

Then use `AskUserQuestion` multiSelect: "Select findings to address:"
- Since findings may exceed 4, implement pagination:
  - First option: "Select all findings" (description: "Address all N findings")
  - Then list individual findings, 3 per page + "Show more" if needed
  - Each finding option: label = short description, description = `file:line — severity`
  - Accumulate selections across pages

If the user selects no findings: inform "No findings selected. Ending review." and stop.

### Step 4: Task Creation

Use `AskUserQuestion`: "How should the selected findings become tasks?"
- "Single task" (description: "One task with all selected findings in description")
- "Group by review mode" (description: "One task per review mode that had selected findings")
- "Separate tasks" (description: "One task per individual finding")

**Determine priority from findings:** Use the highest severity among selected findings — high severity → `high` priority, medium → `medium`, low → `low`.

**For single task:**

```bash
./aiscripts/aitask_create.sh --batch --commit --name "<sanitized_target>_code_review" \
  --desc-file - --priority <p> --effort <e> --type feature --labels "review" <<'TASK_DESC'
## Code Review Findings

<formatted list of all selected findings with file:line, description, severity, and suggested fix>
TASK_DESC
```

Read back the created task file:
```bash
git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

**For multiple tasks (group by mode or separate):**

1. Create a parent task:
   ```bash
   ./aiscripts/aitask_create.sh --batch --commit --name "<sanitized_target>_code_review" \
     --desc-file - --priority <p> --effort medium --type feature --labels "review" <<'TASK_DESC'
   Code review of <target area>. Child tasks contain individual findings grouped by <mode/finding>.
   TASK_DESC
   ```

2. Read back parent task ID:
   ```bash
   git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
   ```

3. Create child tasks — for each group (mode or individual finding):
   ```bash
   ./aiscripts/aitask_create.sh --batch --commit --parent <parent_num> --no-sibling-dep \
     --name "<child_name>" --desc-file - --priority <p> --effort <e> --type feature --labels "review" <<'TASK_DESC'
   <findings for this group/finding with file:line, description, severity, and suggested fix>
   TASK_DESC
   ```

### Step 5: Decision Point

**Profile check:** If the active profile has `review_auto_continue` set to `true`:
- Display: "Profile '\<name\>': continuing to implementation"
- Skip the AskUserQuestion below and proceed directly to the handoff

**Default when `review_auto_continue` is not defined:** `false` (always ask the user).

**If single task was created:**

Use `AskUserQuestion`: "Task created successfully. How would you like to proceed?"
- "Continue to implementation" (description: "Start implementing the fixes now via the standard workflow")
- "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

**If multiple tasks (parent + children) were created:**

Use `AskUserQuestion`: "Tasks created. How would you like to proceed?"
- "Pick one to start" (description: "Select a child task to implement now")
- "Save all for later" (description: "Tasks saved — pick them up later with /aitask-pick <parent_N>")

**If "Pick one to start":** Use `AskUserQuestion` to let the user select which child task, then hand off that child.

**If "Save for later" / "Save all for later":**
- Inform user: "Tasks saved. Run `/aitask-pick <N>` when you want to implement."
- End the workflow.

### Step 6: Hand Off to Shared Workflow

When continuing to implementation, set the following context variables from the selected task, then read and follow `.claude/skills/task-workflow/SKILL.md` starting from **Step 3: Task Status Checks**:

- **task_file**: Path to the task file (e.g., `aitasks/t42_codebase_code_review.md` or `aitasks/t42/t42_1_fix_naming.md`)
- **task_id**: The task number (e.g., `42` or `42_1`)
- **task_name**: The filename stem (e.g., `t42_codebase_code_review` or `t42_1_fix_naming`)
- **is_child**: `true` if a child task was selected from a parent+children review, `false` for single task
- **parent_id**: Parent task number if child (e.g., `42`), null otherwise
- **parent_task_file**: Path to parent task file if child (e.g., `aitasks/t42_codebase_code_review.md`), null otherwise
- **active_profile**: The execution profile loaded in Step 0a (or null if no profile)
- **previous_status**: `Ready`
- **folded_tasks**: Empty list (review does not fold tasks)

---

## Notes

- This skill creates tasks from code review findings — either a single standalone task or a parent with children
- Review modes are loaded from `aitasks/metadata/reviewmodes/*.md` (installed via `ait setup` from t129_3)
- The frontmatter format is: `name` (string), `description` (string), `environment` (optional list)
- Universal modes have no `environment` field and apply to any project type
- Environment auto-detection is best-effort — modes are sorted by relevance but all are available for selection
- The `review_default_modes` profile key pre-selects modes (comma-separated names matching the `name` frontmatter field)
- The `review_auto_continue` profile key controls whether to ask about continuing to implementation (default: `false`, always ask)
- When handing off to task-workflow, the created task has status `Ready` — task-workflow's Step 4 will set it to `Implementing`
- For the full Execution Profiles schema and customization guide, see `.claude/skills/task-workflow/SKILL.md`
